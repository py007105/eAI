"""Baseline brains for the benchmark. Same executor, policy, verification and scoring as EternalAI; only the brain differs.

* ThresholdRestartEngine: fixed thresholds on error ratio, latency and "not scraped"; on a hit it restarts the worst service.
  No diagnosis, no ranking, no learning.
* PrototypeRulesEngine: the project's earlier prototype (EternalAI_prototype_v2, brain/detect.py + brain/diagnose.py +
  brain/engine.py action map) ported onto THIS stack's signals. Ported verbatim: the z-score detector with its floors, minimum
  gaps, streak of 3 and 120-sample normal baseline; the "symptomatic / blame a service only if nothing below it is sick" root
  rule; the cause rules; the action map (memory/CPU/error/latency/down -> restart, disk -> cleanup, bad deploy -> rollback).
  Adapted: input signals come from this app's Prometheus metrics (the prototype read per-replica snapshots), CPU is in
  percent of one core, memory/disk trend uses forecast_exhaustion instead of the prototype's linear predictor, and the
  traffic-surge planner and forest are omitted (no surge action exists here). It is therefore "the prototype's rules on this
  stack", not the prototype's code running unchanged.

Select with ETERNALAI_BRAIN=eternalai|threshold_restart|prototype_rules (see eternalai/api.py). Baselines run in autopilot.
"""
from __future__ import annotations

import time
from collections import deque

import numpy as np

from . import config
from .engine import Engine
from .forecast import forecast_exhaustion

SCRATCH_LIMIT_MB = config.SCRATCH_LIMIT_BYTES / 1e6


def _report(summary: str, cause: str, runbook: str | None) -> dict:
    return {"summary": summary, "evidence_ids": [], "likely_cause": cause, "alternative_causes": [],
            "runbook_id": runbook, "missing_information": []}


def _tail_mean(series, n=3) -> float:
    v = series.dropna().tail(n)
    return float(v.mean()) if len(v) else float("nan")


# ====================================================================== threshold + restart
class ThresholdRestartEngine(Engine):
    use_models = False
    ERR_RATIO, P95_S = 0.20, 0.5

    def _observe(self):
        feats, scores, anom = super()._observe()
        for s in config.SERVICES:
            df = self.frames[s]
            req, err = _tail_mean(df["req_rate"]), _tail_mean(df["err_rate"])
            err_ratio = err / req if req and req > 0.5 else 0.0
            p95 = _tail_mean(df["p95_s"])
            up = _tail_mean(df["up"])
            bad = (not np.isfinite(up)) or up < 0.5 or err_ratio > self.ERR_RATIO or (np.isfinite(p95) and p95 > self.P95_S)
            anom[s] = bool(bad)
            self.latest[s]["anomalous"] = bool(bad)
            feats[s]["_severity"] = 10.0 if (not np.isfinite(up) or up < 0.5) else err_ratio + (p95 if np.isfinite(p95) else 0)
        return feats, scores, anom

    def _predictive(self, feats, now):   # no forecasting in this baseline
        return

    def _diagnose(self, inc, feats, scores, anom):
        # the flags may already have cleared by now (a blip): fall back to the services that confirmed the incident
        hot = sorted((s for s, a in anom.items() if a) or inc.services, key=lambda s: -feats[s].get("_severity", 0))
        inc.ranking = [{"service": s, "score": round(feats[s].get("_severity", 0), 3)} for s in hot]
        inc.likely_cause, inc.confidence, inc.abstained = "insufficient_evidence", None, False   # it does not diagnose
        inc.report = _report(f"Threshold rule fired on {hot[0] if hot else '?'}; restarting it.", "insufficient_evidence",
                             "restart_service")
        inc.report_meta, inc.diagnosed = {"provider": "threshold-rule"}, True
        inc.log(f"threshold rule fired on {hot}")
        self._propose(inc, hot[0], "restart_service")


# ====================================================================== prototype rules, ported
ZSCORE_METRICS = {"p95": {"floor": 12.0, "min_gap": 40.0}, "err": {"floor": 0.015, "min_gap": 0.06},
                  "cpu": {"floor": 6.0, "min_gap": 35.0}, "mem": {"floor": 4.0, "min_gap": 45.0}}
Z_LIMIT, STREAK_NEEDED, WARMUP_POINTS, DEPLOY_WINDOW_S = 3.0, 3, 15, 300
ACTIONS = {"memory_leak": "restart_service", "disk_filling": "clear_temp_path", "down": "restart_service",
           "cpu_runaway": "restart_service", "error_spike": "restart_service", "latency_spike": "restart_service",
           "overload": "restart_service", "bad_deploy": "rollback_release"}
PRIORITY = ["down", "bad_deploy", "memory_leak", "disk_filling", "cpu_runaway", "overload", "error_spike", "latency_spike"]


class ZScoreDetector:
    """Port of the prototype's brain/detect.py ZScoreDetector (same constants and logic)."""

    def __init__(self):
        self.baseline, self.streak = {}, {}

    def update(self, svc, metric, value):
        if value is None or not np.isfinite(value):
            return {"z": 0.0, "hot": False, "anomalous": False, "mean": None}
        cfg, key = ZSCORE_METRICS[metric], (svc, metric)
        base = self.baseline.setdefault(key, deque(maxlen=120))
        if len(base) < WARMUP_POINTS:
            base.append(value)
            return {"z": 0.0, "hot": False, "anomalous": False, "mean": None}
        arr = np.array(base)
        mean, std = float(arr.mean()), max(float(arr.std()), cfg["floor"])
        z = (value - mean) / std
        hot = z > Z_LIMIT and (value - mean) > cfg["min_gap"]
        self.streak[key] = self.streak.get(key, 0) + 1 if hot else 0
        if not hot:                      # learn "normal" only from values that looked normal
            base.append(value)
        return {"z": z, "hot": hot, "anomalous": self.streak[key] >= STREAK_NEEDED, "mean": mean}


def downstream(svc, topology=config.TOPOLOGY):
    seen, stack = set(), list(topology.get(svc, []))
    while stack:
        s = stack.pop()
        if s not in seen:
            seen.add(s)
            stack.extend(topology.get(s, []))
    return seen


def upstream(svc, topology=config.TOPOLOGY):
    return {s for s in topology if svc in downstream(s, topology)}


def proto_find(snaps, z, preds, down_streak, deploys, rps_baseline, now, topology=config.TOPOLOGY):
    """Port of the prototype's diagnose.find(): returns (findings, roots, symptomatic)."""
    symptomatic = {s for s in topology if down_streak.get(s, 0) >= 2 or z.get(s, {}).get("p95", {}).get("anomalous")
                   or z.get(s, {}).get("err", {}).get("anomalous")}
    roots = {s for s in symptomatic if not (downstream(s, topology) & symptomatic)}
    findings = []

    def add(svc, kind, evidence):
        findings.append({"service": svc, "kind": kind, "evidence": evidence,
                         "impacted": sorted(upstream(svc, topology) & symptomatic) if svc in roots or kind in ("down", "bad_deploy")
                         else [], "is_root": True})

    for svc, snap in snaps.items():
        zs, kinds = z.get(svc, {}), set()
        if down_streak.get(svc, 0) >= 2:
            add(svc, "down", [f"no replica of {svc} is answering"])
            continue
        mp = preds.get(svc, {}).get("mem")
        if mp or zs.get("mem", {}).get("anomalous"):
            add(svc, "memory_leak", [f"memory {snap['mem']:.0f} MB of {snap['mem_limit']:.0f} MB"])
            kinds.add("memory_leak")
        dp = preds.get(svc, {}).get("disk")
        if dp or (snap["disk_limit"] and snap["disk"] >= 0.9 * snap["disk_limit"]):
            add(svc, "disk_filling", [f"disk {snap['disk']:.0f} MB of {snap['disk_limit']:.0f} MB"])
            kinds.add("disk_filling")
        traffic_up = snap["rps"] > 1.5 * max(rps_baseline.get(svc, 0.0), 1.0)
        if zs.get("cpu", {}).get("anomalous"):
            if traffic_up:
                add(svc, "overload", [f"CPU {snap['cpu']:.0f}%, traffic well above normal"])
                kinds.add("overload")
            else:
                add(svc, "cpu_runaway", [f"CPU {snap['cpu']:.0f}%, traffic is normal"])
                kinds.add("cpu_runaway")
        if svc in roots:
            if zs.get("err", {}).get("anomalous"):
                dep = deploys.get(svc)
                if dep and now - dep < DEPLOY_WINDOW_S:
                    add(svc, "bad_deploy", [f"errors started {int(now - dep)} s after a deployment"])
                    kinds.add("bad_deploy")
                elif "disk_filling" not in kinds:
                    add(svc, "error_spike", [f"{snap['err'] * 100:.0f}% of requests failing"])
                    kinds.add("error_spike")
            if zs.get("p95", {}).get("anomalous") and not kinds & {"overload", "cpu_runaway"}:
                if traffic_up:
                    add(svc, "overload", [f"p95 {snap['p95']:.0f} ms with traffic well above normal"])
                elif "memory_leak" not in kinds:
                    add(svc, "latency_spike", [f"p95 {snap['p95']:.0f} ms"])
    return findings, roots, symptomatic


class PrototypeRulesEngine(Engine):
    use_models = False

    def __init__(self, mode: str = "autopilot"):
        super().__init__(mode)
        self.zd, self.down_streak, self.deploys, self.rps_norm, self._proto = ZScoreDetector(), {}, {}, {}, None

    def _predictive(self, feats, now):   # the prototype acted on forecasts too, but only through its own predictor; omitted
        return

    def _observe(self):
        feats, scores, anom = super()._observe()
        now, snaps, z = time.time(), {}, {}
        for s in config.SERVICES:
            df = self.frames[s]
            req, err = _tail_mean(df["req_rate"]), _tail_mean(df["err_rate"])
            limit = _tail_mean(df["mem_limit_bytes"], 1)
            vals = {"p95": _tail_mean(df["p95_s"]) * 1000.0, "err": (err / req) if req and req > 0.5 else 0.0,
                    "cpu": _tail_mean(df["cpu_cores"]) * 100.0, "mem": _tail_mean(df["mem_bytes"]) / 1e6}
            z[s] = {m: self.zd.update(s, m, v) for m, v in vals.items()}
            up = _tail_mean(df["up"])
            self.down_streak[s] = 0 if (np.isfinite(up) and up >= 0.5) else self.down_streak.get(s, 0) + 1
            if (feats[s].get("deploys_3m") or 0) > 0 and s not in self.deploys:
                self.deploys[s] = now
            if (feats[s].get("deploys_3m") or 0) == 0:
                self.deploys.pop(s, None)
            if not z[s]["p95"]["hot"] and not z[s]["err"]["hot"] and np.isfinite(req):
                self.rps_norm.setdefault(s, deque(maxlen=120)).append(req)
            snaps[s] = {"mem": vals["mem"], "mem_limit": limit / 1e6 if np.isfinite(limit) else 0.0,
                        "disk": _tail_mean(df["scratch_bytes"]) / 1e6 if np.isfinite(_tail_mean(df["scratch_bytes"])) else 0.0,
                        "disk_limit": SCRATCH_LIMIT_MB, "rps": req if np.isfinite(req) else 0.0, "err": vals["err"],
                        "p95": vals["p95"], "cpu": vals["cpu"]}
        self._proto = (snaps, z, now)
        preds = self._preds()
        _, _, symptomatic = proto_find(snaps, z, preds, self.down_streak, self.deploys, self._rps_base(), now)
        for s in config.SERVICES:
            anom[s] = s in symptomatic or bool(preds.get(s)) or snaps[s]["disk"] >= 0.9 * SCRATCH_LIMIT_MB \
                or z[s]["cpu"]["anomalous"] or z[s]["mem"]["anomalous"]
            self.latest[s]["anomalous"] = bool(anom[s])
        return feats, scores, anom

    def _rps_base(self):
        return {s: float(np.mean(v)) for s, v in self.rps_norm.items() if len(v)}

    def _preds(self):
        out = {}
        for s in config.SERVICES:
            df = self.frames[s]
            m = forecast_exhaustion(df["mem_bytes"], _tail_mean(df["mem_limit_bytes"], 1))
            d = forecast_exhaustion(df["scratch_bytes"], config.SCRATCH_LIMIT_BYTES)
            out[s] = {"mem": {"slope": m["slope_per_min"] / 6e7, "eta_s": m["eta_s"]} if m else None,
                      "disk": {"slope": d["slope_per_min"] / 6e7, "eta_s": d["eta_s"]} if d else None}
        return out

    def _diagnose(self, inc, feats, scores, anom):
        snaps, z, now = self._proto
        findings, roots, symptomatic = proto_find(snaps, z, self._preds(), self.down_streak, self.deploys,
                                                  self._rps_base(), now)
        findings = [f for f in findings if f["service"] in roots or f["kind"] in ("memory_leak", "disk_filling", "cpu_runaway")]
        findings.sort(key=lambda f: PRIORITY.index(f["kind"]) if f["kind"] in PRIORITY else 99)
        inc.diagnosed = True
        inc.report_meta = {"provider": "prototype-rules"}
        if not findings:
            inc.ranking = [{"service": s, "score": 1.0} for s in sorted(symptomatic)] or [{"service": config.SERVICES[0], "score": 0.0}]
            inc.likely_cause, inc.abstained = "insufficient_evidence", True
            inc.report = _report("The prototype's rules found no matching cause.", "insufficient_evidence", None)
            self._propose(inc, inc.ranking[0]["service"], None)
            return
        top = findings[0]
        order = [top["service"]] + [f["service"] for f in findings[1:] if f["service"] != top["service"]]
        inc.ranking = [{"service": s, "score": round(1 / (i + 1), 3)} for i, s in enumerate(order)]
        cause = {"disk_filling": "disk_fill", "cpu_runaway": "unseen_fault", "overload": "unseen_fault"}.get(top["kind"], top["kind"])
        cause = {"down": "down"}.get(cause, cause)
        inc.likely_cause, inc.confidence, inc.abstained = cause, None, False
        rb = ACTIONS[top["kind"]]
        inc.report = _report("; ".join(top["evidence"]), cause, rb)
        inc.log(f"prototype rules: {top['kind']} on {top['service']}")
        self._propose(inc, top["service"], rb)
