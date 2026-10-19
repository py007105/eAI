"""Render docs/results/demo_rehearsal_R4.md from the saved R4 records (read-only copies; every number computed here).

    python scripts/render_r4.py [--dir results/rehearsals/R4] [--out docs/results/demo_rehearsal_R4.md]

Inputs, copied read-only after the presenter finished: the evaluator's truth files and scored rows (truth/), the brain's incidents, audit log, status,
and the evaluator's scorecard. R4 is a rehearsal: it enters no benchmark count and is reported apart from the frozen v2 statistics.
"""
import argparse
import json
import time
from pathlib import Path

ORDER = ["8e7b5f1436", "fbc8f2f45f", "26d7614e46", "87745c4b3c"]
REPORTED_BY_PRESENTER = {"fbc8f2f45f", "26d7614e46", "87745c4b3c"}
CUTOFF, FREEZE = "21:10 IST", "23:10 IST"   # assumed deadlines from the brief (freeze 23:10; rehearsals at least 2 h before)


def ts(x):
    return time.strftime("%H:%M:%S", time.localtime(x)) + f".{int((x % 1) * 10)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/rehearsals/R4")
    ap.add_argument("--out", default="docs/results/demo_rehearsal_R4.md")
    a = ap.parse_args()
    d = Path(a.dir)
    rows = {r["run_id"]: r for r in (json.loads(x) for x in (d / "truth" / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
    truth = {r: json.loads((d / "truth" / f"{r}.json").read_text(encoding="utf-8")) for r in ORDER}
    incs = json.loads((d / "brain_incidents.json").read_text(encoding="utf-8"))
    audit = json.loads((d / "brain_audit.json").read_text(encoding="utf-8"))
    sc = json.loads((d / "scorecard.json").read_text(encoding="utf-8"))
    mode = json.loads((d / "brain_status.json").read_text(encoding="utf-8"))["mode"]
    L = ["# Demo rehearsal R4 (presenter, real browser, Ask first; rendered by `scripts/render_r4.py`)", "",
         f"R4 is a rehearsal, not a benchmark run: it enters no evaluated count and is kept apart from the frozen v2 statistics. Every attempt the evaluator scored is listed "
         f"({sc['runs']} runs on the scorecard). **R4 ran after the assumed rehearsal cutoff ({CUTOFF}) and finished after the assumed freeze ({FREEZE}).** "
         f"Brain mode when the records were copied: {mode}.", "",
         "| # | run | scenario / target (revealed) | injected (IST) | incident | s inject to incident | proposal (runbook → service) | proposal pending (IST) | outcome of proposal | "
         "s inject to verified recovery | failed-request % | evaluator: detected / recovered / abstained correctly / harmful | reported by presenter |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(ORDER, 1):
        t, s = truth[r], rows[r]
        mine = [i for i in incs if t["t_inject"] - 1 <= i["opened_t"] <= s["t_end"]]
        inc = mine[0] if mine else None
        act = inc["actions"][0] if inc and inc["actions"] else None
        exp = next((e["t"] for e in (inc or {}).get("timeline", []) if "expired" in e["msg"]), None)
        end = act.get("executed_t") if act and act.get("executed") else exp
        L.append(f"| {n} | {r} | {t['scenario']} / {t['target']} | {ts(t['t_inject'])} | {inc['id'] + ' (' + inc['likely_cause'] + ')' if inc else 'none'} | "
                 f"{round(inc['opened_t'] - t['t_inject'], 1) if inc else '-'} | {act['runbook_id'] + ' → ' + act['service'] if act else 'none'} | "
                 f"{ts(act['t']) + ' to ' + ts(end) if act and end else '-'} | "
                 f"{('executed, approved_by ' + str(act['approved_by'])) if act and act.get('executed') else (act['verdict'] if act else ('abstained' if inc and inc['abstained'] else '-'))} | "
                 f"{s.get('time_to_verified_recovery_s') or '-'} | {s['failed_request_pct']} | {s['detected']} / {s.get('recovered')} / {s.get('abstained_correctly')} / "
                 f"{s.get('harmful_interventions')} | {'yes' if r in REPORTED_BY_PRESENTER else 'no (found on the scorecard)'} |")
    L += ["", "Approval audit (brain `/audit`, the only entries in this brain process):", ""]
    L += [f"- {ts(e['t'])}: {e['runbook']} on {e['service']} by {e['actor']}, ok={e['ok']}, result {e['result']}" for e in audit]
    L += ["", "Incidents outside the four challenge windows (opened with no challenge's injection window covering them; cause unverified, not fault detections):", ""]
    wins = [(truth[r]["t_inject"] - 1, rows[r]["t_end"]) for r in ORDER]
    for i in incs:
        if not any(lo <= i["opened_t"] <= hi for lo, hi in wins):
            L.append(f"- {i['id']} {ts(i['opened_t'])} on {', '.join(i['services'])}: {i['likely_cause']}, abstained {i['abstained']}, {i['status']}, {len(i['actions'])} actions")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
