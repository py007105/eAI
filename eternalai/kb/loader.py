"""Load and validate data/kb/ (scripts/build_kb.py). A missing or invalid knowledge base is reported, never guessed."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

KB_DIR = Path(os.getenv("EAI_KB_DIR") or Path(__file__).resolve().parents[2] / "data" / "kb")
REQUIRED = {
    "knowledge_base.csv": {"fault_type", "name", "category", "description", "symptoms", "eternalai_action", "sources",
                           "reviewed_by_team", "source_sheet"},
    "fix_options.csv": {"fault_type", "rank_prior", "fix_id", "fix", "risk", "automation", "source_sheet"},
    "fix_catalog.csv": {"fix_id", "fix", "what_it_does"},
    "outcomes_prototype.csv": {"fault_type", "fix_id", "recovered", "failed_pct", "environment"},
    "outcomes_measured.csv": {"live_label", "fix", "recovered", "failed_request_pct", "time_to_verified_recovery_s",
                              "source_file", "policy"},
}
RISKS = {"low", "medium", "high"}


class KBError(ValueError):
    pass


@dataclass
class KB:
    path: Path
    knowledge: pd.DataFrame
    options: pd.DataFrame
    catalog: pd.DataFrame
    prototype: pd.DataFrame
    measured: pd.DataFrame
    manifest: dict

    def entry(self, plan_fault: str) -> dict | None:
        rows = self.knowledge[self.knowledge.fault_type == plan_fault]
        if rows.empty:
            return None
        r = rows.iloc[0].to_dict()
        r["reviewed"] = str(r.get("reviewed_by_team", "")).strip().lower() == "yes"
        return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in r.items()}

    def summary(self) -> dict:
        return {"path": str(self.path), "faults": int(self.knowledge.fault_type.nunique()), "fix_options": len(self.options),
                "measured_runs": len(self.measured), "prototype_runs": len(self.prototype),
                "unreviewed_rows": int((self.knowledge.reviewed_by_team.astype(str).str.lower() != "yes").sum()),
                "workbook_sha256": self.manifest.get("workbook_sha256")}


def load_kb(path: Path | str | None = None) -> KB | None:
    """None when the directory does not exist (the engine then uses its fixed table); KBError when it exists but is invalid."""
    p = Path(path) if path else KB_DIR
    if not p.exists():
        return None
    frames = {}
    for name, cols in REQUIRED.items():
        f = p / name
        if not f.exists():
            raise KBError(f"{name} missing in {p}")
        df = pd.read_csv(f)
        missing = cols - set(df.columns)
        if missing:
            raise KBError(f"{name}: missing columns {sorted(missing)}")
        frames[name] = df
    bad = set(frames["fix_options.csv"].risk.dropna().astype(str).str.lower()) - RISKS
    if bad:
        raise KBError(f"fix_options.csv: unknown risk values {sorted(bad)}")
    srcless = int(frames["knowledge_base.csv"].sources.isna().sum())
    if srcless:
        raise KBError(f"knowledge_base.csv: {srcless} rows without sources (plan §10.9: every external row keeps its source)")
    man = p / "MANIFEST.json"
    return KB(p, frames["knowledge_base.csv"], frames["fix_options.csv"], frames["fix_catalog.csv"],
              frames["outcomes_prototype.csv"], frames["outcomes_measured.csv"],
              json.loads(man.read_text(encoding="utf-8")) if man.exists() else {})
