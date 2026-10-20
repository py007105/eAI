"""The EternalAI loop: observe -> detect -> diagnose -> (policy) -> act -> verify -> report.

One tick every ~2 s. The engine never sees evaluator ground truth. Models are loaded from saved
artifacts; if one is missing the engine says so (`status.models`) and uses explicit rule
fallbacks instead of silently pretending.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import artifacts, config
from .classify import ABSTAIN, CAUSE_RUNBOOKS, rule_diagnose
from .collector import DockerView, Prom
from .dedupe import ReleaseGrace, Suppressor, downstream_of
from .detect import Persistence, service_anomalous
from .executor import ExecutionError, Executor
from .features.window import fit_baseline, window_features
from .investigate import Investigator, remember_verified
from .llm import llm_enabled, make_report, template_report
from .policy import PolicyEngine
from .rca import deepest_anomalous, evidence_table
from .verify import verify_recovery

CLOSED = ("recovered", "partially_recovered", "unresolved", "escalated")
EVIDENCE_DIR = Path("runtime/evidence")


@dataclass
class Incident:
    id: str
    opened_t: float
    kind: str = "reactive"           # reactive | predicted
    status: str = "open"
    closed_t: float | None = None
    services: list = field(default_factory=list)
    ranking: list = field(default_factory=list)
    likely_cause: str = "pending"
    confidence: float | None = None
    abstained: bool = False
    report: dict | None = None
    report_meta: dict | None = None
    evidence: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    verification: dict | None = None
    timeline: list = field(default_factory=list)
    forecasts: list = field(default_factory=list)
    diagnosis: dict | None = None   # v2: top class, abstention reason, novelty, limits exceeded (see _diagnose)
    diagnosed: bool = False
    before: dict | None = None      # measured when the incident was diagnosed
    after: dict | None = None       # measured after the verification window

    def log(self, msg):
        self.timeline.append({"t": time.time(), "msg": msg})

    def public(self) -> dict:
        d = {k: getattr(self, k) for k in ("id", "opened_t", "closed_t", "kind", "status", "services", "ranking",
                                          "likely_cause", "confidence", "abstained", "report", "report_meta",
                                          "actions", "verification", "timeline", "forecasts", "diagnosis", "before", "after")}
        d["evidence"] = [{"id": e.id, "tool": e.tool, "service": e.service, "summary": e.summary} for e in self.evidence]
        return d


class Engine:
    use_models = True   # baseline engines (eternalai/baselines.py) set this False and never load trained artifacts

    def __init__(self, mode: str | None = None):
        self.prom, self.dv = Prom(), DockerView()
        self.executor, self.policy = Executor(), PolicyEngine(mode)
        self.persist = Persistence(3)
        self.grace, self.suppress = ReleaseGrace(config.DEPLOY_GRACE_S), Suppressor()
        self.incidents: list[Incident] = []
        self.first_anom: dict = {}
        self.latest: dict = {}      # service -> {"features", "score", "anomalous", "state"}
        self.depfail: dict = {}
        self.lock = threading.RLock()
        self._stop = threading.Event()
        if self.use_models:
            self.detectors, self.det_meta = artifacts.load("detectors")
            self.classifier, self.cls_meta = artifacts.load("classifier")
            self.ranker, self.rank_meta = artifacts.load("ranker")
            self.baselines = (artifacts.load("baselines")[0]) or {}
        else:
            self.detectors = self.classifier = self.ranker = None
            self.det_meta = self.cls_meta = self.rank_meta = None
            self.baselines = {}
        # The feature window must be the one the models were trained with (train/serve consistency).
        self.window_s = float((self.cls_meta or self.det_meta or {}).get("window_s", 30.0))
        self.models_loaded = {"detectors": self.detectors is not None, "classifier": self.classifier is not None,
                              "ranker": self.ranker is not None, "baselines": bool(self.baselines)}
        self.busy: set[str] = set()   # services with an action in flight
        self.last_closed: dict = {}

    # ------------------------------------------------------------ observation
    def _observe(self):
        states = self.dv.poll()
        feats, scores, anom, raw = {}, {}, {}, {}
        frames, failed = {}, {}
        for s in config.SERVICES:
            df = self.prom.signals(s, 150)
            frames[s] = df
            failed[s] = list(df.attrs.get("failed_queries", []))
            base = self.baselines.get(s) or fit_baseline(df.iloc[: len(df) // 2])  # live fallback, flagged in status
            f = window_features(df, base, self.window_s)
            st = states.get(s)
            if "up" in failed[s]:
                # The `up` QUERY failed (Prometheus error), which says nothing about the service: judge "down" from Docker only.
                # Otherwise a monitoring outage would make every healthy service look down (and open incidents on them).
                down = st is not None and not st.running
            else:
                down = (st is not None and not st.running) or f.get("up_frac") == 0 or not np.isfinite(f.get("up_frac", np.nan))
            if self.detectors and s in self.detectors:
                sc = self.detectors[s].score(f)
                a = service_anomalous(self.detectors[s], f, down)
            else:
                sc, a = float("nan"), down or rule_diagnose(f) != "healthy"
            feats[s], scores[s], raw[s] = f, sc, (bool(a), st)
        # A normal rolling release restarts the service for a few seconds. Judge it only once the grace period is over, and
        # judge its CALLERS the same way: they fail only because of that blip, and flagging them first opened an incident on
        # the wrong service with the real root still "healthy" in the evidence (found by the live smoke test).
        now = time.time()
        in_grace = {s: self.grace.in_grace(s, feats[s].get("deploys_3m"), now) for s in config.SERVICES}
        for s in config.SERVICES:
            a, st = raw[s]
            if in_grace[s] or any(in_grace[d] for d in downstream_of(s)):
                a = False
            anom[s] = bool(a)
            f, sc = feats[s], scores[s]
            self.latest[s] = {"features": {k: (None if not np.isfinite(v) else round(float(v), 4))
                                           for k, v in f.items() if not k.endswith("_obs")},
                              "score": None if not np.isfinite(sc) else round(sc, 4), "anomalous": bool(a),
                              "state": {"running": st.running, "image_tag": st.image_tag} if st else None}
        self.frames = frames
        self.telemetry_failed = {s: q for s, q in failed.items() if q}   # reported by /status; empty when all queries worked
        return feats, scores, anom

    def _app_snapshot(self, probe: bool) -> dict:
        """User-facing measurements: app-wide error ratio and web p95 over the last 10 s, plus (optionally)
        the success rate of a few synthetic checkouts made right now."""
        from .verify import checkout_probe
        import httpx
        req = self.prom.instant('sum(rate(http_requests_total{service="web"}[10s]))')
        err = self.prom.instant('sum(rate(http_requests_total{service="web",status=~"5.."}[10s]))')
        p95 = self.prom.instant('histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="web"}[10s])))')
        snap = {"error_ratio": (err / req) if req and req == req and err == err else None,
                "p95_s": None if p95 != p95 else p95}
        if probe:
            with httpx.Client() as c:
                res = [checkout_probe(c, timeout=1.5).ok for _ in range(3)]
            snap["checkout_success"] = sum(res) / len(res)
        return snap

    def _depfail(self):
        d = {}
        for caller, callees in config.TOPOLOGY.items():
            for c in callees:
                d[(caller, c)] = self.prom.instant(
                    f'sum(rate(dependency_calls_total{{service="{caller}",target="{c}",outcome="error"}}[10s]))')
        self.depfail = {k: (None if v != v else v) for k, v in d.items()}
        return {k: (0.0 if v is None else v) for k, v in self.depfail.items()}

    # ------------------------------------------------------------ main tick
    def tick(self):
        now = time.time()
        feats, scores, anom = self._observe()
        for s, a in anom.items():
            if a and s not in self.first_anom:
                self.first_anom[s] = now
            if not a:
                self.first_anom.pop(s, None)
        confirmed = {s for s in anom if self.persist.update(s, anom[s])}
        # do not re-open an incident every few seconds for an anomaly that already ended unresolved or escalated
        for inc in self.incidents[-20:]:
            if inc.closed_t and not getattr(inc, "_noted", False):
                self.suppress.note_incident(inc.status, inc.services)
                inc._noted = True
        self.suppress.update(anom)
        confirmed = self.suppress.filter(confirmed)
        to_diagnose = None
        with self.lock:
            self._expire_pending(now)
            # v2: an incident waiting for approval does not block detection. Services it already covers are not re-opened
            # (no duplicate proposal for the same ongoing anomaly); anomalies elsewhere open their own incident.
            covered, stack = set(), [s for i in self.incidents if i.status == "awaiting_approval" for s in i.services]
            while stack:  # a pending incident also explains the callers of its services (they fail because of it)
                s = stack.pop()
                if s not in covered:
                    covered.add(s)
                    stack.extend(config.CALLERS.get(s, []))
            confirmed = confirmed - covered
            open_inc = next((i for i in self.incidents if i.status == "open"), None)
            active = [i for i in self.incidents if i.status in ("open", "verifying", "executing")]
            if confirmed and not active and now - self.last_closed.get("t", 0) > 8:
                inc = Incident(uuid.uuid4().hex[:8], now)
                inc.log(f"anomaly confirmed on {sorted(confirmed)}")
                self.incidents.append(inc)
                open_inc = inc
            if open_inc is not None:
                open_inc.services = sorted(set(open_inc.services) | confirmed)
                # An incident opens ~6 s after onset (3 persistent ticks). Diagnose once a full feature window lies after
                # the onset, because the classifier was trained on such windows only.
                if not open_inc.diagnosed and now - open_inc.opened_t >= max(4.0, self.window_s - 4.0):
                    to_diagnose = open_inc
        if to_diagnose is not None:   # outside the lock: the API must not wait on telemetry and Docker calls
            self._try_diagnose(to_diagnose, feats, scores, anom)
        if not open_inc:
            self._predictive(feats, now)

    def reset_run_state(self) -> dict:
        """v2 (harness independence): forget per-run state so the next benchmark run starts clean. v1 carried a cooldown from one run into the
        next (a restart was blocked 'last action 85 s ago' by the previous run's action). Incident history is kept; open or pending incidents are
        escalated and closed. Refused while an action is executing or being verified."""
        with self.lock:
            busy = [i.id for i in self.incidents if i.status in ("executing", "verifying")]
            if busy:
                raise ValueError(f"action in flight for incident(s) {busy}; try again when they finish")
            now, closed = time.time(), []
            for inc in self.incidents:
                if inc.status in ("open", "awaiting_approval"):
                    inc.status, inc.closed_t = "escalated", now
                    inc.log("reset between runs: incident closed")
                    self._preserve(inc)
                    closed.append(inc.id)
            cleared = {"cooldown_services": sorted(self.policy.history), "breakers": sorted(self.policy.breaker_open),
                       "actions_this_hour": len(self.policy.executed)}
            self.policy.history.clear()
            self.policy.executed = []
            self.policy.breaker_open.clear()
            self.suppress, self.persist = Suppressor(), Persistence(3)
            self.first_anom.clear()
            self.last_closed = {}
            return {"reset": True, "closed_incidents": closed, "cleared": cleared}

    def _expire_pending(self, now: float):
        """v2: escalate a proposal that was not approved within APPROVAL_TTL_S, and close a watch-only observation after the
        same time. Called with the lock held. In v1 neither ever expired, so one unapproved proposal blocked all detection."""
        for inc in self.incidents:
            if not inc.actions:
                continue
            act = inc.actions[-1]
            waiting = inc.status == "awaiting_approval" or (inc.status == "open" and inc.diagnosed and act.get("verdict") == "observe_only")
            if not waiting or now - act["t"] < config.APPROVAL_TTL_S:
                continue
            watch = act.get("verdict") == "observe_only"
            if not watch:
                act["verdict"] = "expired_unapproved"
            inc.status, inc.closed_t = "escalated", now
            inc.log("watch-only: observation window ended; escalated with evidence preserved" if watch else
                    f"no approval within {config.APPROVAL_TTL_S:.0f} s: proposal expired, escalated to a human with evidence preserved")
            self._preserve(inc)

    # ------------------------------------------------------------ diagnosis
    def _try_diagnose(self, inc: Incident, feats, scores, anom):
        """An exception during diagnosis must never leave an incident 'open' forever (an open incident blocks all new
        ones): escalate it with the error recorded and the evidence preserved.

        Called WITHOUT the engine lock. EternalAI's own `_diagnose` does its slow work (Prometheus queries, Docker calls, log
        reads, evidence building, model inference) unlocked and takes the lock only to read and write incident state, so the
        API (/approvals, /incidents) never waits on telemetry. The benchmark baseline brains override `_diagnose` and were
        written for the old contract (called under the lock); they keep it, unchanged."""
        try:
            if type(self)._diagnose is Engine._diagnose:
                self._diagnose(inc, feats, scores, anom)
            else:
                with self.lock:
                    self._diagnose(inc, feats, scores, anom)
        except Exception as e:
            with self.lock:
                self.last_error = f"diagnosis failed: {type(e).__name__}: {e}"
                inc.diagnosed = True
                inc.status, inc.closed_t = "escalated", time.time()
                inc.log(f"diagnosis failed ({type(e).__name__}); escalated to a human")
                self._preserve(inc)

    def _diagnosis_record(self, root: str, p, feats_root: dict) -> dict:
        """v2 item B: keep what v1 threw away (the top class behind an abstention, why it abstained, how novel the window was,
        which learned healthy limits were exceeded), so a run can be explained from its own row."""
        top = max(p.probs, key=p.probs.get) if p.probs else None
        det = (self.detectors or {}).get(root)
        return {"root": root, "top_class": top, "top_probability": round(p.probs[top], 6) if top else None,
                "answered_label": p.label, "abstain_reason": p.reason or None,
                "novelty": None if p.novelty is None else round(float(p.novelty), 4),
                "novelty_threshold": getattr(getattr(self.classifier, "gate", None), "threshold_", None),
                "abstain_below": self.classifier.abstain_below,
                "limits_exceeded": det.out_of_range(feats_root) if det is not None else None}

    def _diagnose(self, inc: Incident, feats, scores, anom):
        """Diagnose `inc`. Called without the lock (see `_try_diagnose`): read state under the lock, compute unlocked, apply
        under the lock. If the incident changed meanwhile (closed by a reset, or diagnosed already), the result is dropped."""
        with self.lock:
            services = list(inc.services)
            onset = {s: self.first_anom.get(s) for s in config.SERVICES}
        d = self._diagnose_compute(services, onset, feats, scores, anom)
        with self.lock:
            if inc.diagnosed or inc.status != "open":
                return
            inc.ranking, inc.diagnosis = d["ranking"], d["diagnosis"]
            inc.likely_cause, inc.confidence, inc.abstained = d["label"], d["confidence"], d["abstained"]
            inc.evidence = d["evidence"]
            # The action never waits for an LLM: the deterministic report and runbook come first, a real LLM
            # report replaces the text later (a live Gemini call took ~7 s in testing).
            inc.report, inc.diagnosed = d["report"].model_dump(), True
            inc.report_meta = {"provider": "template", "llm_pending": llm_enabled()}
            inc.log(f"diagnosed {d['label']} on {d['root']}")
            self._propose(inc, d["root"], d["report"].runbook_id if not d["abstained"] else None)
            self._llm_upgrade_async(inc, d["ctx"])

    def _diagnose_compute(self, services: list, onset: dict, feats, scores, anom) -> dict:
        """The slow part of a diagnosis, run WITHOUT the engine lock: Prometheus (dependency failures), Docker (state, logs),
        evidence building, ranking and classification. Touches no shared incident state."""
        depfail = self._depfail()
        table = evidence_table(scores, anom, onset, depfail, feats)
        if self.ranker:
            ranking = self.ranker.rank(table)
        else:  # fallback: old-prototype style rule, flagged in status
            order = deepest_anomalous(anom) or list(config.SERVICES)
            ranking = [{"service": s, "score": round(1 / (i + 1), 3)} for i, s in enumerate(order)]
        root = ranking[0]["service"]
        inv = Investigator(self.prom, self.dv)
        for s in {root, *services}:
            inv.metrics(s, feats[s]); inv.container(s); inv.error_logs(s); inv.deploy_history(s)
        inv.dependency_failures(depfail)
        inv.forecast(root, self.frames[root])
        # classification of the suspected root service
        st = self.dv.state().get(root)
        if self.classifier:
            p = self.classifier.predict(feats[root])
            label, conf, abst, probs = p.label, p.confidence, p.abstained, p.probs
            diagnosis = self._diagnosis_record(root, p, feats[root])
        else:
            label, conf, abst, probs = rule_diagnose(feats[root]), None, False, {}
            diagnosis = {"root": root, "rule_label": label}
        if st is not None and not st.running and st.oom_killed:
            label, abst = "memory_leak", False  # container was OOM-killed: direct evidence
        if label == "healthy":                  # anomalous but classified healthy => do not guess
            label, abst = ABSTAIN, True
        inv.similar_incidents(label if not abst else "unknown fault")
        alts = [c for c, v in sorted(probs.items(), key=lambda kv: -kv[1]) if c not in ("healthy", label)][:2]
        cands = [] if abst else list(CAUSE_RUNBOOKS.get(label, []))
        ctx = {"cause": label, "confidence": conf or 0.0, "candidates": cands, "alternatives": alts,
               "ranking": ranking[:3], "evidence": [{"id": e.id, "tool": e.tool, "summary": e.summary} for e in inv.items]}
        return {"ranking": ranking, "root": root, "diagnosis": diagnosis, "label": label, "confidence": conf,
                "abstained": abst, "evidence": inv.items, "ctx": ctx, "report": template_report(ctx)}

    def _llm_upgrade_async(self, inc: Incident, ctx: dict):
        if not llm_enabled():
            return

        def work():
            t0 = time.time()
            rep, meta = make_report(ctx)
            meta = {**meta, "latency_s": round(time.time() - t0, 2), "llm_pending": False}
            with self.lock:
                if meta["provider"] != "template":
                    report = rep.model_dump()
                    meta["llm_runbook_suggestion"] = report["runbook_id"]
                    if inc.actions:  # keep the report consistent with what was actually proposed
                        report["runbook_id"] = inc.actions[-1]["runbook_id"]
                    inc.report = report
                inc.report_meta = meta
                inc.log(f"report by {meta['provider']} ({meta['latency_s']}s)")
        threading.Thread(target=work, daemon=True).start()

    def _propose(self, inc: Incident, service: str, runbook: str | None):
        if runbook is None:
            inc.status, inc.closed_t = "escalated", time.time()
            inc.log("no safe automatic action: escalated to a human with evidence preserved")
            self._preserve(inc)
            return
        d = self.policy.evaluate(runbook, service, fault=inc.likely_cause, user_impact=self._user_impact())
        act = {"t": time.time(), "runbook_id": runbook, "service": service, "verdict": d.verdict,
               "reason": d.reason, "risk": d.risk, "executed": False, "approved_by": None}
        inc.actions.append(act)
        inc.log(f"policy: {d.verdict} - {d.reason}")
        if d.verdict == "execute":
            self._run_async(inc, act, actor="autopilot")
        elif d.verdict == "needs_approval":
            inc.status = "awaiting_approval"
        elif d.verdict == "observe_only":
            inc.status = "open"   # watch-only: stays open, nothing executed
        else:  # blocked
            inc.status, inc.closed_t = "escalated", time.time()
            self._preserve(inc)

    def _user_impact(self) -> bool | None:
        """Are users affected? The entry services (no callers) are anomalous. None if not observed yet."""
        entries = [s for s in config.SERVICES if not config.CALLERS.get(s)]
        seen = [self.latest[s].get("anomalous") for s in entries if s in self.latest]
        return any(bool(a) for a in seen) if seen else None

    # ------------------------------------------------------------ act + verify
    def approve(self, inc_id: str, approver: str):
        with self.lock:
            inc = next((i for i in self.incidents if i.id == inc_id), None)
            if not inc or inc.status != "awaiting_approval":
                raise ValueError("no pending approval for that incident")
            if self.policy.kill_switch:
                raise ValueError("kill switch is on: nothing is executed, not even approved actions")
            act = next(a for a in reversed(inc.actions) if a["verdict"] == "needs_approval" and not a["executed"])
            act["approved_by"] = approver
        self._run_async(inc, act, actor=f"human:{approver}")

    def reject(self, inc_id: str, approver: str):
        with self.lock:
            inc = next((i for i in self.incidents if i.id == inc_id), None)
            if not inc or inc.status != "awaiting_approval":
                raise ValueError("no pending approval for that incident")
            inc.actions[-1]["verdict"] = f"rejected_by_{approver}"
            inc.status, inc.closed_t = "escalated", time.time()
            inc.log(f"rejected by {approver}; escalated")
            self._preserve(inc)

    def _run_async(self, inc, act, actor):
        inc.status = "executing"
        threading.Thread(target=self._act_and_verify, args=(inc, act, actor), daemon=True).start()

    def _act_and_verify(self, inc: Incident, act: dict, actor: str):
        svc = act["service"]
        inc.before = self._app_snapshot(probe=True)  # measured just before acting, with short timeouts
        try:
            res = self.executor.run(act["runbook_id"], svc, actor, [e.id for e in inc.evidence][:6], reason=act.get("reason", ""))
            act["executed"], act["result"], act["executed_t"] = True, res, time.time()
            self.policy.record_execution(svc)
            inc.log(f"executed {act['runbook_id']} on {svc} by {actor}")
        except ExecutionError as e:
            act["error"] = str(e)
            inc.log(f"execution failed: {e}")
            inc.status, inc.closed_t = "escalated", time.time()
            self._preserve(inc)
            return
        inc.status = "verifying"
        time.sleep(3)
        v = verify_recovery(config.OBSERVATION_S)
        v["t"] = time.time()
        inc.verification = v
        inc.after = self._app_snapshot(probe=False) | {"checkout_success": v["success_rate"]}
        inc.log(f"verification: {v['outcome']} ({v['success_rate']:.0%} of {v['probes']} checkouts)")
        log_v = getattr(self.executor, "log_verification", None)
        if log_v:
            log_v(inc.id, act["runbook_id"], svc, v["outcome"], v["success_rate"])
        if v["outcome"] == "recovered":
            self.policy.record_recovered(svc)
            inc.status, inc.closed_t = "recovered", time.time()
            remember_verified(inc.likely_cause, svc, (inc.report or {}).get("summary", ""), act["runbook_id"])
        else:
            inc.status = v["outcome"] if v["outcome"] != "unresolved" else "unresolved"
            inc.closed_t = time.time()
            self._preserve(inc)  # stop repeated interventions; policy breaker handles the rest
        self.last_closed = {"t": time.time()}
        self.persist.runs.clear()
        self.first_anom.clear()

    def _preserve(self, inc: Incident):
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / f"{inc.id}.json").write_text(json.dumps(inc.public(), default=str, indent=1))
        self.last_closed = {"t": time.time()}

    # ------------------------------------------------------------ prediction
    def _predictive(self, feats, now):
        """Open a 'predicted' incident when memory or disk growth is steady and exhaustion is near."""
        with self.lock:
            if any(i.status in ("open", "awaiting_approval", "verifying", "executing") for i in self.incidents):
                return
        inv = Investigator(self.prom, self.dv)
        for s in config.SERVICES:
            for e in inv.forecast(s, self.frames[s]):
                f = e.data
                if f["eta_earliest_s"] < config.PREDICT_HORIZON_S and f["share_of_limit_now"] > 0.25:
                    cause = "memory_leak" if f["resource"] == "memory" else "disk_fill"
                    inv.metrics(s, feats[s]); inv.container(s); inv.deploy_history(s)   # Docker/telemetry: outside the lock
                    ranking = [{"service": s, "score": 1.0}]
                    cands = CAUSE_RUNBOOKS[cause]
                    ctx = {"cause": cause, "confidence": 0.0, "candidates": cands, "alternatives": [],
                           "ranking": ranking, "evidence": [
                               {"id": x.id, "tool": x.tool, "summary": x.summary} for x in inv.items]}
                    rep = template_report(ctx)
                    with self.lock:
                        if any(i.status in ("open", "awaiting_approval", "verifying", "executing") for i in self.incidents):
                            return   # a reactive incident opened meanwhile; it takes precedence
                        inc = Incident(uuid.uuid4().hex[:8], now, kind="predicted", services=[s])
                        inc.ranking, inc.likely_cause, inc.forecasts = ranking, cause, [f]
                        inc.confidence = None
                        inc.log(f"forecast: {f['resource']} exhaustion in {f['eta_earliest_s']:.0f}-{f['eta_latest_s']:.0f}s")
                        inc.evidence = inv.items
                        inc.report, inc.diagnosed = rep.model_dump(), True
                        inc.report_meta = {"provider": "template", "llm_pending": llm_enabled()}
                        self.incidents.append(inc)
                        self._propose(inc, s, rep.runbook_id)
                        self._llm_upgrade_async(inc, ctx)
                    return

    # ------------------------------------------------------------ loop
    def run_forever(self, interval=2.0):
        while not self._stop.is_set():
            t0 = time.time()
            try:
                self.tick()
            except Exception as e:  # keep the loop alive; the error is visible in status
                self.last_error = f"{type(e).__name__}: {e}"
                self.last_error_t = time.time()
            time.sleep(max(0.0, interval - (time.time() - t0)))

    def stop(self):
        self._stop.set()

    last_error: str | None = None
    last_error_t: float | None = None
