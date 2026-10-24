"""Outcome-ranked fix choice (plan §9.5): "no crash > recovered > fewer failed requests > faster recovery"; where nothing
is measured, the knowledge-base prior is used and flagged.

Evidence tiers, best first:
  measured_here       runs of THIS stack's benchmarks where the fix ran on the injected service (data/kb/outcomes_measured.csv)
  measured_prototype  the old prototype's runs in the workbook (local processes, a different system)
  prior               the knowledge base's rank prior (drafted with AI help; flagged unreviewed until the team reviews it)
  fixed_table         this repository's fixed table (eternalai/classify.CAUSE_RUNBOOKS), when nothing else applies
Within a tier: higher recovered share, then fewer failed requests, then faster recovery. "No crash" is not recorded by
this stack's benchmarks, so it is not used; that is stated, not assumed. Only fixes that map to an implemented runbook
can be proposed for execution; the others are returned as suggest-only (runbook_id None) and never proposed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from ..classify import CAUSE_RUNBOOKS
from .labels import FIX_TO_RUNBOOK, LIVE_TO_PLAN
from .loader import KB

TIERS = ("measured_here", "measured_prototype", "prior", "fixed_table")


@dataclass
class Fix:
    key: str                       # runbook id, or the KB fix id for suggest-only fixes
    runbook_id: str | None         # None: suggest only (not executable here)
    name: str
    evidence: str                  # one of TIERS
    n: int = 0
    recovered_share: float | None = None
    failed_pct_mean: float | None = None
    recovery_s_median: float | None = None
    kb_rank_prior: int | None = None
    kb_risk: str | None = None
    kb_automation: str | None = None
    kb_fix_ids: list = field(default_factory=list)
    sources: list = field(default_factory=list)

    def public(self) -> dict:
        return asdict(self)


def _num(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else round(float(v), 4)


def _stats(df: pd.DataFrame, rec_col: str, fail_col: str, time_col: str | None):
    rec = df[rec_col].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0", "yes"))
    return (len(df), round(float(rec.mean()), 4), _num(pd.to_numeric(df[fail_col], errors="coerce").mean()),
            _num(pd.to_numeric(df[time_col], errors="coerce").median()) if time_col else None)


def ranked_fixes(kb: KB | None, live_label: str) -> list[Fix]:
    plan = LIVE_TO_PLAN.get(live_label)
    cands: dict[str, Fix] = {}
    for rb in CAUSE_RUNBOOKS.get(live_label, []):
        cands[rb] = Fix(rb, rb, rb, "fixed_table", sources=["eternalai/classify.py CAUSE_RUNBOOKS"])
    if kb is not None and plan is not None:
        for _, o in kb.options[kb.options.fault_type == plan].sort_values("rank_prior").iterrows():
            rb = FIX_TO_RUNBOOK.get(o.fix_id)
            key = rb or str(o.fix_id)
            f = cands.setdefault(key, Fix(key, rb, str(o.fix), "prior"))
            f.kb_fix_ids.append(str(o.fix_id))
            if f.kb_rank_prior is None:
                f.kb_rank_prior, f.kb_risk, f.kb_automation = int(o.rank_prior), str(o.risk), str(o.automation)
            if f.evidence == "fixed_table":
                f.evidence = "prior"
            f.sources.append("data/kb/fix_options.csv (knowledge base, unreviewed)")
        for f in cands.values():
            if f.runbook_id is None:
                continue
            m = kb.measured[(kb.measured.live_label == live_label) & (kb.measured.fix == f.runbook_id)]
            if len(m):
                f.n, f.recovered_share, f.failed_pct_mean, f.recovery_s_median = _stats(
                    m, "recovered", "failed_request_pct", "time_to_verified_recovery_s")
                f.evidence = "measured_here"
                f.sources.append("data/kb/outcomes_measured.csv: " + "; ".join(sorted(set(m.policy.astype(str)))))
                continue
            proto_ids = [fid for fid, rb in FIX_TO_RUNBOOK.items() if rb == f.runbook_id]
            p = kb.prototype[(kb.prototype.fault_type == plan) & (kb.prototype.fix_id.isin(proto_ids))]
            if len(p):
                f.n, f.recovered_share, f.failed_pct_mean, _ = _stats(p, "recovered", "failed_pct", None)
                f.evidence = "measured_prototype"
                f.sources.append("data/kb/outcomes_prototype.csv (old prototype, local processes)")
    order = {rb: i for i, rb in enumerate(CAUSE_RUNBOOKS.get(live_label, []))}

    def sort_key(f: Fix):
        return (f.runbook_id is None, TIERS.index(f.evidence), -(f.recovered_share or 0.0),
                f.failed_pct_mean if f.failed_pct_mean is not None else 1e9,
                f.recovery_s_median if f.recovery_s_median is not None else 1e9,
                f.kb_rank_prior if f.kb_rank_prior is not None else 99, order.get(f.key, 99))
    return sorted(cands.values(), key=sort_key)


def ranked_runbooks(kb: KB | None, live_label: str) -> list[str]:
    """Executable runbooks in ranked order; the fixed table when no knowledge base is loaded or nothing maps."""
    out = [f.runbook_id for f in ranked_fixes(kb, live_label) if f.runbook_id]
    return out or list(CAUSE_RUNBOOKS.get(live_label, []))
