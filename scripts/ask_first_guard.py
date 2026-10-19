"""Ask-first validity guard for the v2 evaluation (read-only watcher; does not edit or import the driver or anything it re-reads).

    python scripts/ask_first_guard.py --raw D:/eAI/eAI-workspace/eAI/results/benchmark-v2/benchmark_v2_raw.jsonl [--no-kill] [--once]

Watches the raw result file. Every new `eternalai_ask_first` row is checked; if one shows that the approval path failed (the invalid-arm
pattern of v1) the guard stops the driver (scripts/stage3_eval.py and its run_benchmark.py child; both are resumable and a killed
in-flight run leaves no row) and writes ALERT lines. Invalid means any of:
  - approver stats with approve_failures, poll_errors or thread_errors above 0 (an approve call that was refused or never reached the brain);
  - an action whose verdict is `expired_unapproved` (a proposal sat unapproved until the TTL: the simulated operator did not approve it);
  - an incident still `awaiting_approval`/pending in the stored row (a proposal that was never decided).
A supported-fault ask-first row with no detection is reported as WARN (not a stop): it may be a legitimate miss, and the three conditions above
say whether the approval path caused it.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PENDING_STATUSES = {"awaiting_approval", "pending", "pending_approval"}
HEALTHY = {"traffic_surge", "good_deploy"}


def check_row(row):
    """Return (problems, warnings) for one raw result row; empty lists for non-ask-first rows."""
    if row.get("arm") != "eternalai_ask_first":
        return [], []
    problems, warnings = [], []
    st = row.get("approver") or {}
    for k in ("approve_failures", "poll_errors", "thread_errors"):
        if (st.get(k) or 0) > 0:
            problems.append(f"approver {k}={st[k]}")
    for inc in row.get("incidents") or []:
        if str(inc.get("status", "")).lower() in PENDING_STATUSES:
            problems.append(f"incident {inc.get('id')} still {inc.get('status')}")
        for act in inc.get("actions") or []:
            if act.get("verdict") == "expired_unapproved":
                problems.append(f"incident {inc.get('id')} proposal {act.get('runbook_id')} expired unapproved")
    if row.get("scenario") not in HEALTHY and not (row.get("score") or {}).get("detected"):
        warnings.append("supported fault not detected")
    return problems, warnings


def stop_driver():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'stage3_eval|stage3_rerun|run_benchmark' } "
          "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force; 'stopped ' + $_.ProcessId }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--no-kill", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=float, default=20.0)
    a = ap.parse_args()
    raw, seen = Path(a.raw), 0
    print(f"[{time.strftime('%H:%M:%S')}] guard watching {raw}", flush=True)
    while True:
        lines = raw.read_text(encoding="utf-8").splitlines() if raw.exists() else []
        for line in lines[seen:]:
            row = json.loads(line)
            problems, warnings = check_row(row)
            tag = f"{row.get('arm')} {row.get('scenario')} seed {row.get('seed')}"
            if row.get("arm") == "eternalai_ask_first":
                print(f"[{time.strftime('%H:%M:%S')}] ask-first row {tag}: {'INVALID' if problems else 'ok'}"
                      f"{' WARN ' + '; '.join(warnings) if warnings else ''}", flush=True)
            if problems:
                print(f"ALERT ask-first invalid ({tag}): {'; '.join(problems)}", flush=True)
                if not a.no_kill:
                    print("ALERT driver stop: " + (stop_driver() or "no driver process found"), flush=True)
                return 2
        seen = len(lines)
        if a.once:
            return 0
        time.sleep(a.poll)


if __name__ == "__main__":
    sys.exit(main())
