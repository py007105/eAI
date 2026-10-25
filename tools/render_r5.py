"""Render docs/results/demo_rehearsal_R5.md from the saved R5 records and the approval captures (every number computed here).

    python tools/render_r5.py [--dir results/rehearsals/R5] [--captures results/rehearsals/R5_capture] [--out docs/results/demo_rehearsal_R5.md]

Inputs (read-only copies): the evaluator's truth files and scored rows, the brain's incidents, audit log and status, the scorecard, and the capture folders
written by tools/approval_capture.py (one JSON line per second: what the brain's GET /approvals returned and what a headless dashboard page showed).
R5 is a rehearsal: it enters no benchmark count and is reported apart from the frozen v2 statistics.
"""
import argparse
import json
import time
from pathlib import Path

ORDER = ["1813a0c878", "aad57af45f", "9118ad85c9", "2cdc9b587b", "81448e49df", "2e9a6526f6", "b9c959c7ec"]
R5B = {"2e9a6526f6", "b9c959c7ec"}   # the R5b session (20 Oct, from 01:40 IST)
# what the presenter reported for each run (their words, abridged); the observer note is theirs, not an inference
PRESENTER = {"1813a0c878": "proposal expired; presenter was not watching", "aad57af45f": "proposal expired; presenter was not watching",
             "9118ad85c9": "0 incidents", "2cdc9b587b": "saw the card and clicked Approve", "81448e49df": "abstained, 0 actions",
             "2e9a6526f6": "0 incidents, 0 actions; presenter was not watching", "b9c959c7ec": "clicked Approve on the dashboard"}


def ts(x):
    return time.strftime("%H:%M:%S", time.localtime(x)) if x else "-"


def load_captures(root):
    lines, folders = [], []
    for d in sorted(Path(root).glob("*/")):
        f = d / "capture.jsonl"
        if f.exists():
            recs = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
            recs = [r for r in recs if "brain" in r]
            folders.append((d.name, recs[0]["t"] if recs else None, recs[-1]["t"] if recs else None, len(recs)))
            lines += [dict(r, folder=d.name) for r in recs]
    return sorted(lines, key=lambda r: r["t"]), folders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/rehearsals/R5")
    ap.add_argument("--captures", default="results/rehearsals/R5_capture")
    ap.add_argument("--out", default="docs/results/demo_rehearsal_R5.md")
    a = ap.parse_args()
    d = Path(a.dir)
    rows = {r["run_id"]: r for r in (json.loads(x) for x in (d / "truth" / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
    truth = {r: json.loads((d / "truth" / f"{r}.json").read_text(encoding="utf-8")) for r in ORDER}
    incs = json.loads((d / "brain_incidents.json").read_text(encoding="utf-8"))
    audit = json.loads((d / "brain_audit.json").read_text(encoding="utf-8"))
    sc = json.loads((d / "scorecard.json").read_text(encoding="utf-8"))
    cap, folders = load_captures(a.captures)
    L = ["# Demo rehearsal R5 (presenter, real browser, Ask first; rendered by `tools/render_r5.py`)", "",
         "R5 is a rehearsal, not a benchmark run: it enters no evaluated count and is kept apart from the frozen v2 statistics. The scorecard was not reset "
         f"after R4, so it holds R4 and R5 together ({sc['runs']} runs); R5 runs are identified by run id. Every R5 run is listed. **R5 is partial:** a manual "
         "Reject and a timed five-minute sequence were not done and are left for a later R5b.", "",
         "## Runs", "",
         "| # | run | scenario / target (revealed) | injected | incident | s inject to incident | proposal | pending (brain timeline) | outcome | "
         "s inject to verified recovery | failed-request % | presenter's report |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    windows = {}
    for n, r in enumerate(ORDER, 1):
        t, s = truth[r], rows[r]
        r_label = f"{r} (R5b)" if r in R5B else r
        inc = next((i for i in incs if t["t_inject"] - 1 <= i["opened_t"] <= s["t_end"]), None)
        act = inc["actions"][0] if inc and inc["actions"] else None
        exp = next((e["t"] for e in (inc or {}).get("timeline", []) if "expired" in e["msg"] or "rejected by" in e["msg"]), None)
        end = act.get("executed_t") if act and act.get("executed") else exp
        if act:
            windows[r] = (act["t"], end, inc["id"])
        outcome = (f"executed, approved_by {act['approved_by']}" if act and act.get("executed") else act["verdict"] if act
                   else ("abstained" if inc and inc["abstained"] else "no incident" if not inc else "-"))
        if act and act["verdict"] == "expired_unapproved":
            outcome += "; **visibility unresolved, observer not watching**" if r in ("1813a0c878", "aad57af45f") else ""
        L.append(f"| {n} | {r_label} | {t['scenario']} / {t['target']} | {ts(t['t_inject'])} | {inc['id'] + ' (' + inc['likely_cause'] + ')' if inc else 'none'} | "
                 f"{round(inc['opened_t'] - t['t_inject'], 1) if inc else '-'} | {act['runbook_id'] + ' → ' + act['service'] if act else 'none'} | "
                 f"{ts(act['t']) + ' to ' + ts(end) + f' ({end - act[chr(116)]:.1f} s)' if act and end else '-'} | {outcome} | "
                 f"{s.get('time_to_verified_recovery_s') or '-'} | {s['failed_request_pct']} | {PRESENTER[r]} |")
    L += ["", "## Brain offer vs dashboard view, per pending window (from the approval captures)", "",
          "Capture folders: " + "; ".join(f"`{f}` {ts(a0)} to {ts(a1)} ({k} lines)" for f, a0, a1, k in folders) + ".", "",
          "The capture reads the brain's `GET /approvals` and a headless page on the dashboard once a second. The headless page goes through the same dashboard "
          "server as the presenter's browser, so it shows what the dashboard served; it does not prove what the presenter's own window displayed.", "",
          "| run | pending window | seconds captured | brain listed this proposal (s) | dashboard showed an Approve button (s) | first brain listing | first dashboard card | "
          "seconds brain listed it but dashboard did not | brain GET errors | messages under the queue on the headless page (it never clicks, so the presenter's click messages are not captured) | screenshots |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in ORDER:
        if r not in windows:
            continue
        w0, w1, iid = windows[r]
        seg = [c for c in cap if w0 <= c["t"] <= (w1 or w0)]
        if not seg:
            L.append(f"| {r} | {ts(w0)} to {ts(w1)} | 0 (no capture running) | - | - | - | - | - | - | - | - |")
            continue
        b = [c for c in seg if any(p["incident_id"] == iid for p in c["brain"]["pending"])]
        dsh = [c for c in seg if (c["dash"].get("approve_buttons") or 0) > 0]
        gap = [c for c in b if not (c["dash"].get("approve_buttons") or 0)]
        msgs = sorted({c["dash"].get("approval_msg") for c in cap if w0 <= c["t"] <= (w1 or w0) + 30 and c["dash"].get("approval_msg")})
        shots = [f"`{c['folder']}/{c['screenshot']}`" for c in seg if c.get("screenshot")]
        L.append(f"| {r} | {ts(w0)} to {ts(w1)} | {len(seg)} | {len(b)} | {len(dsh)} | {ts(b[0]['t']) if b else '-'} | {ts(dsh[0]['t']) if dsh else '-'} | "
                 f"{len(gap)} | {sum(c['brain']['code'] != 200 for c in seg)} | {'; '.join(msgs) or '-'} | {', '.join(shots[:4]) + (' …' if len(shots) > 4 else '') or '-'} |")
    L += ["", "Runs without a proposal, during capture:", ""]
    for r in ORDER:
        if r in windows:
            continue
        t, s = truth[r], rows[r]
        seg = [c for c in cap if t["t_inject"] <= c["t"] <= s["t_end"]]
        L.append(f"- {r} ({t['scenario']}): {len(seg)} captured seconds between injection and the end of scoring; brain listed a proposal in "
                 f"{sum(bool(c['brain']['pending']) for c in seg)}, dashboard showed an Approve button in {sum((c['dash'].get('approve_buttons') or 0) > 0 for c in seg)}.")
    L += ["", "Incidents during R5 and R5b that opened outside every run's scoring window (cause unverified; not fault detections; the evaluator did not count them):", ""]
    first = min(truth[r]["t_inject"] for r in ORDER)
    wins = {r: (truth[r]["t_inject"] - 1, rows[r]["t_end"]) for r in ORDER}
    for i in incs:
        if i["opened_t"] < first or any(lo <= i["opened_t"] <= hi for lo, hi in wins.values()):
            continue
        prev = max((r for r in ORDER if rows[r]["t_end"] <= i["opened_t"]), key=lambda r: rows[r]["t_end"], default=None)
        rel = f"{i['opened_t'] - rows[prev]['t_end']:.0f} s after the end of {prev}'s scoring window" if prev else "before the first R5 run"
        L.append(f"- {i['id']} {ts(i['opened_t'])} on {', '.join(i['services'])}: {i['likely_cause']}, abstained {i['abstained']}, {i['status']}, "
                 f"{len(i['actions'])} actions; opened {rel}")
    r5_audit = [e for e in audit if e["t"] >= min(truth[r]["t_inject"] for r in ORDER)]
    L += ["", "Approval audit entries during R5 (brain `/audit`):", ""] + [f"- {ts(e['t'])}: {e['runbook']} on {e['service']} by {e['actor']}, ok={e['ok']}" for e in r5_audit]
    L += ["", "## Notes", "",
          "- The two expiries (1813a0c878, aad57af45f) ran before the capture tool existed. They are recorded as **visibility unresolved, observer not watching**: "
          "the presenter was not watching the dashboard and cannot say what the watcher window showed. They are not classified as a dashboard defect or as "
          "operator error.",
          "- The watcher one-liner given for R5 always printed PENDING on Windows PowerShell 5.1: `@(Invoke-RestMethod …)` wraps an empty JSON array into a "
          "one-element array, so `.Count` was never 0. Corrected form (prints PENDING only when a proposal is pending): "
          "`while ($true) { $a = @((Invoke-RestMethod http://localhost:8000/approvals) | Where-Object { $_ }); if ($a.Count) { \"$(Get-Date -f HH:mm:ss) PENDING\"; "
          "$a | Select-Object incident_id, service, runbook_id | Format-Table } else { \"$(Get-Date -f HH:mm:ss) none pending\" }; Start-Sleep 2 }`. "
          "`tools/approval_capture.py` replaces it for evidence.",
          "- Audit form: every dashboard approval is logged by the brain with actor `human:dashboard`, while the incident's action records "
          "`approved_by: dashboard`. Both come from the same call (`engine/engine.py`: `approve()` stores the approver name; the executor is given "
          "`actor=f\"human:{approver}\"`), so they are the same approval, not a difference in how it was made.",
          "- **OPEN (not done in R5 or R5b): Reject clicked by hand; the five-minute sequence timed end to end; a fallback recording.**"]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
