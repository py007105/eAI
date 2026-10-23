"""Build the knowledge-base files for Package C (plan §9.5, §10.2 parts B and C) into data/kb/.

    python scripts/build_kb.py --workbook <path to EternalAI_training_dataset_v1.xlsx>

Reads the owner's workbook READ-ONLY (never copied into the repository) and this repository's benchmark raw files, and
writes only what fix choice needs:
  data/kb/knowledge_base.csv     sheet B_knowledge_base (all columns, including `sources` and `reviewed_by_team`)
  data/kb/fix_options.csv        sheet B_fix_options (fault x fix, rank prior, risk, automation)
  data/kb/fix_catalog.csv        sheet B_fix_catalog
  data/kb/outcomes_prototype.csv sheet C_outcome_runs (the old prototype's runs: local processes, not this stack)
  data/kb/outcomes_measured.csv  per run of THIS stack's benchmarks where a fix was executed on the injected service
  data/kb/MANIFEST.json          input SHA256s, row counts, the policy each benchmark ran under
Every workbook-derived row gets `source_sheet` and `source_workbook_sha256`; every measured row gets `source_file` and
`policy`. No telemetry, no training rows and no incident text are copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "kb"
SHEETS = {"B_knowledge_base": "knowledge_base.csv", "B_fix_options": "fix_options.csv", "B_fix_catalog": "fix_catalog.csv",
          "C_outcome_runs": "outcomes_prototype.csv"}
# This stack's benchmark files and the policy each ran under (eternalai/rulebooks/benchmark-v2.yaml reproduces both:
# autopilot executed low and medium risk; recreate and rollback were medium, so they ran without approval).
BENCHMARKS = [("results/benchmark-v1/benchmark_raw.jsonl", "benchmark-system-v1 policy (equivalent to rulebooks/benchmark-v2.yaml)"),
              ("results/benchmark-v2/rerun/benchmark_v2_evaluated.jsonl", "benchmark-system-v2 policy (rulebooks/benchmark-v2.yaml)")]
SCENARIO_LABEL = {"crash": "down", "latency": "latency_spike", "error_spike": "error_spike", "memory_leak": "memory_leak",
                  "disk_fill": "disk_fill", "bad_deploy": "bad_deploy"}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def measured_rows() -> list[dict]:
    rows = []
    for rel, policy in BENCHMARKS:
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            label = SCENARIO_LABEL.get(r["scenario"])
            if label is None:
                continue
            fix = None
            for inc in r.get("incidents") or []:
                for a in inc.get("actions") or []:
                    if a.get("executed") and a.get("service") == r.get("target"):
                        fix = a.get("runbook_id")
                        break
                if fix:
                    break
            s = r.get("score") or {}
            rows.append({"live_label": label, "scenario": r["scenario"], "arm": r["arm"], "seed": r["seed"], "target": r.get("target"),
                         "fix": fix or "no_action", "recovered": s.get("recovered"), "failed_request_pct": s.get("failed_request_pct"),
                         "time_to_verified_recovery_s": s.get("time_to_verified_recovery_s"), "source_file": rel, "policy": policy})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", required=True)
    a = ap.parse_args()
    wb = Path(a.workbook)
    digest = sha256(wb)
    OUT.mkdir(parents=True, exist_ok=True)
    x = pd.ExcelFile(wb)
    manifest = {"built_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workbook_name": wb.name,
                "workbook_sha256": digest, "files": {}}
    for sheet, name in SHEETS.items():
        df = x.parse(sheet).assign(source_sheet=sheet, source_workbook_sha256=digest)
        df.to_csv(OUT / name, index=False)
        manifest["files"][name] = {"rows": len(df), "from": f"workbook sheet {sheet}"}
    m = pd.DataFrame(measured_rows())
    m.to_csv(OUT / "outcomes_measured.csv", index=False)
    manifest["files"]["outcomes_measured.csv"] = {"rows": len(m), "from": [
        {"file": rel, "sha256": sha256(ROOT / rel), "policy": pol} for rel, pol in BENCHMARKS]}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v["rows"] for k, v in manifest["files"].items()}))


if __name__ == "__main__":
    main()
