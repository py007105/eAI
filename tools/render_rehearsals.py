"""Render docs/results/demo_rehearsals.md from the rehearsal records (every number computed here).

    python tools/render_rehearsals.py [--dir results/rehearsals] [--out docs/results/demo_rehearsals.md]

Inputs: R1.json and R2.json (tools/rehearsal.py, headless) and, if present, R3_monitor.jsonl (tools/r3_monitor.py, passive recorder for the human-driven run) with
R3_results.jsonl (the evaluator's scorecard rows for the runs since the stack start, copied read-only). All three rehearsals are reported, whatever happened.
"""
import argparse
import json
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None


def f(x):
    return "-" if x is None else x


def headless(d, name, what):
    L = [f"## {name}: {what}", "", f"Brain at start: {d['brain']}. Total {d['total_s']} s. Emulated dashboard polls: {d['emulated_dashboard_polls']} requests, {d['emulated_dashboard_errors']} errors "
         "(an emulation of the dashboard's REST polling, not the real dashboard)." if d.get("emulated_dashboard_polls") else f"Brain at start: {d['brain']}. Total {d['total_s']} s.", "",
         "| challenge | mode | scenario (revealed) | target | s to first incident | s to verified recovery | s from start to scorecard | min free RAM GB | Gemini requests | report provider(s) | executed | incidents | recovered | failed-request % | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in d["steps"]:
        if s.get("error"):
            L.append(f"| {s['label']} | - | - | - | - | - | - | - | - | - | - | - | - | - | ERROR: {s['error']} |")
            continue
        notes = []
        if s.get("fallback_reasons"):
            notes.append("LLM fallback: " + ", ".join(s["fallback_reasons"]))
        if s.get("flakiness"):
            notes.append("flaky: " + ", ".join(s["flakiness"]))
        if s.get("incidents_opened", 0) and s.get("incidents_opened") > 1:
            notes.append(f"{s['incidents_opened']} incidents for one fault")
        if s.get("rejected") is not None:
            notes.append(f"proposal rejected (HTTP {s['rejected']})")
        L.append(f"| {s['label']} | {s['mode']} | {s['revealed_scenario']}{' (hidden draw)' if s.get('scenario_hidden_until_reveal') else ''} | {s['target']} | {f(s['s_to_first_incident'])} | "
                 f"{f(s['s_to_verified_recovery'])} | {s['s_start_to_scorecard']} | {s['min_free_ram_gb']} | {s['gemini_requests']} | {', '.join(map(str, s['providers'])) or '-'} | "
                 f"{', '.join(s['executed']) or '-'} | {s['incidents_opened']} | {f(s['recovered'])} | {s['failed_request_pct']} | {'; '.join(notes) or '-'} |")
    cp = [s for s in d["steps"] if s.get("revealed_scenario") == "cpu_burn"]
    for s in cp:
        L += ["", "cpu_burn (unseen) record: " + json.dumps({"diagnosis": s["diagnosis"], "proposals": s["proposals"], "abstained_correctly": s["abstained_correctly"],
                                                              "actions_executed": s["actions_executed"]}, default=str)[:900]]
    return L


R3_WINDOW = (1792409701.9, 1792411115.0)   # from the R3 launcher's restock to just before the R3b launcher started (epoch s)
R3_PRESENTER = ("Reported by the presenter (R3, real browser): a token pasted from terminal text gave 'Mode not changed (0): Invalid leading whitespace, reserved "
                "character(s)...' (the message repeated the header value); in the unseen segment the amber nodes were web, orders and inventory, payments green; "
                "no approval card, only 'escalated: insufficient evidence'; the causes chart had inventory far ahead (margin 0.95); the report said 'written by gemini "
                "(LLM disagreed; engine diagnosis kept)'; 'Likely cause: insufficient evidence (100% calibrated)' was shown. A disk_fill run appeared that the presenter did "
                "not start by script.")


def inject_to_card(log, r, truth_dir):
    """Lower bound: the driver did not record the absolute start time, only s_start_to_card. The start came after the previous log event (plus the
    driver's 20 s pause after a draw without a proposal), so card time >= that + s_start_to_card; t_inject is the evaluator's truth for the run."""
    tf = Path(truth_dir) / f"{r['run_id']}.json"
    i = next((k for k, e in enumerate(log) if e.get("run_id") == r["run_id"] and e.get("event", "").endswith("_path")), None)
    if not tf.exists() or not i:
        return "-"
    prev = log[i - 1]
    t_start_min = prev["t"] + (20 if prev.get("event") == "draw_without_proposal" else 0)
    return (f"at least {t_start_min + r['s_start_to_card'] - json.loads(tf.read_text(encoding='utf-8'))['t_inject']:.1f} (a LOWER BOUND, not an exact measurement: "
            "the driver did not record the absolute start time)")


def r3b(d, truth_dir):
    if not d:
        return ["## R3b: automated in the real dashboard (headless Chromium, below-normal priority, throwaway token)", "", "Not recorded yet."]
    L = ["## R3b: automated in the real dashboard (headless Chromium, below-normal priority, throwaway token)", "",
         f"Started {d['started']}; free RAM at start {d['free_ram_gb_start']} GB." + (f" **Stopped: {d['stopped']}.**" if d.get("stopped") else ""), "",
         "Token handling (mode change from the dashboard):", "",
         f"- wrong token: `{d.get('msg_wrong_token')}`", f"- token with a non-Latin-1 character: `{d.get('msg_non_latin1_token')}`",
         f"- throwaway token, Ask first: `{d.get('msg_correct_token') or '(no error)'}`; brain mode afterwards: {d.get('brain_mode_after')}", ""]
    log = d.get("log", [])
    draws = [e for e in log if e.get("event") == "draw_without_proposal"]
    for e in draws:
        L.append(f"- draw without a proposal ({e['path']} path, draw {e['draw']}): {e['reveal'].get('scenario')} on {e['reveal'].get('target')}, incidents {e['reveal'].get('incidents_opened')}")
    for key in ("approve", "reject"):
        r = d.get(key)
        if not r:
            L += ["", f"### {key.title()} path", "", "No proposal within the draw limit."]
            continue
        L += ["", f"### {key.title()} path (draw {r['draw']})", "", f"- card read from the page: `{' | '.join(r['card_text'].splitlines())}`",
              f"- anomalous services when the card appeared: {', '.join(r['anomalous_at_card'])}",
              f"- s from fault injection to card: {inject_to_card(log, r, truth_dir)}; s from card to click: {r['s_card_to_click']}; message after click: `{r['click_message']}`",
              f"- s from the challenge start to card: {r['s_start_to_card']} (includes the evaluator's settle wait before injecting: 45 s, or 200 s after a release change)"]
        if key == "approve":
            L.append(f"- verification banner: `{r.get('banner')}`; s from click to banner: {r.get('s_click_to_banner')} (after R3b the banner text was changed to "
                     "\"Verified by EternalAI's own synthetic checkout\" and the tagline to \"Detect. Diagnose. Recover. Verify.\"; the R3b screenshots show the old wording)")
        else:
            L.append(f"- incident status after reject: {r.get('incident_status_after_reject')}; actions: {r.get('actions_after_reject')}")
        L += [f"- reveal: {r['reveal']}", f"- free RAM after: {r['free_ram_gb']} GB", f"- screenshots: {', '.join('docs/screenshots/' + s for s in r['screenshots'])}"]
    u = d.get("unseen")
    if u:
        L += ["", "### Unseen fault (cpu_burn, ask-first)", "", f"- approval card: {('`' + ' | '.join(u['card_text'].splitlines()) + '` (rejected)') if u['card_text'] else 'none'}",
              f"- report panel: `{' | '.join(u['report_text'].splitlines())}`", f"- causes margin: `{u['margin_text']}`",
              f"- incidents: {u['incidents']}", f"- reveal: {u['reveal']}", f"- free RAM after: {u['free_ram_gb']} GB",
              f"- screenshots: {', '.join('docs/screenshots/' + s for s in u['screenshots'])}"]
    return L


def r3(dir_):
    mon = Path(dir_) / "R3_monitor.jsonl"
    if not mon.exists():
        return ["## R3: human-driven, real browser", "", "Not recorded yet."]
    recs = [json.loads(x) for x in mon.read_text(encoding="utf-8").splitlines() if x.strip()]
    recs = [r for r in recs if R3_WINDOW[0] <= r["t"] <= R3_WINDOW[1]]
    ram = [r["free_ram_gb"] for r in recs]
    t0 = recs[0]["t"]
    L = ["## R3: human-driven, real browser, dashboard open", "", f"Recorder: {len(recs)} samples over {recs[-1]['t'] - t0:.0f} s; minimum free RAM with the browser open: **{min(ram)} GB** "
         f"(at the start {ram[0]} GB).", "", R3_PRESENTER, "", "| incident | opened (s after the R3 stack start) | statuses seen | cause | abstained | proposal seen (service, runbook) | ranking at the time | anomalous services when the proposal was pending | final |",
         "|---|---|---|---|---|---|---|---|---|"]
    seen, order = {}, []
    for r in recs:
        s = r.get("state")
        if not s:
            continue
        pend = {a["incident_id"]: a for a in (s["approvals"] or [])}
        for i in s["incidents"]:
            if i["opened_t"] < R3_WINDOW[0]:
                continue
            e = seen.setdefault(i["id"], {"opened": i["opened_t"], "statuses": [], "prop": None, "anom": None, "rank": None})
            if i["id"] not in order:
                order.append(i["id"])
            if not e["statuses"] or e["statuses"][-1] != i["status"]:
                e["statuses"].append(i["status"])
            e.update(cause=i["likely_cause"], abst=i["abstained"], final=i["status"], rank=i["ranking"][:3] if i["ranking"] else e["rank"])
            if i["id"] in pend and e["prop"] is None:
                a = pend[i["id"]]
                e["prop"], e["anom"] = f"{a['service']}, {a['runbook_id']}", s["anomalous"]
    for iid in order:
        e = seen[iid]
        rk = ", ".join(f"{x['service']} {x['score']:.2f}" for x in (e["rank"] or []))
        L.append(f"| {iid} | {e['opened'] - t0:.0f} | {' > '.join(e['statuses'])} | {e.get('cause')} | {e.get('abst')} | {e['prop'] or '-'} | {rk or '-'} | "
                 f"{', '.join(e['anom']) if e['anom'] is not None else '-'} | {e.get('final')} |")
    res = Path(dir_) / "R3_results.jsonl"
    if res.exists():
        L += ["", "Evaluator rows for the runs started during R3 (scorecard after the launcher's reset):", "",
              "| scenario | target | detected | time to detect s | recovered | s to verified recovery | failed-request % | actions executed | abstained correctly |", "|---|---|---|---|---|---|---|---|---|"]
        for x in (json.loads(l) for l in res.read_text(encoding="utf-8").splitlines() if l.strip()):
            L.append(f"| {x.get('scenario')} | {x.get('target')} | {x.get('detected')} | {f(x.get('time_to_detect_s'))} | {f(x.get('recovered'))} | {f(x.get('time_to_verified_recovery_s'))} | "
                     f"{x.get('failed_request_pct')} | {x.get('actions_executed')} | {f(x.get('abstained_correctly'))} |")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/rehearsals")
    ap.add_argument("--out", default="docs/results/demo_rehearsals.md")
    a = ap.parse_args()
    L = ["# Demo rehearsals (rendered by `tools/render_rehearsals.py`; all three are reported)", "",
         "Each rehearsal started from the launcher (`tools/demo.ps1 -ConfirmReset`): export checksums verified first, scorecard volume reset through the launcher's confirm path, stack "
         "started under T3 with the dashboard on, inventory restocked, preflight passed. Rehearsals are not benchmark runs and enter no evaluated count.", ""]
    r1, r2 = load(Path(a.dir) / "R1.json"), load(Path(a.dir) / "R2.json")
    if r1:
        L += headless(r1, "R1", "LLM on (`gemini-3.5-flash-lite`), headless, scripted operator") + [""]
    if r2:
        L += headless(r2, "R2", "keys removed (`-NoLlm`), headless: template fallback") + [""]
    L += r3(a.dir) + [""] + r3b(load(Path(a.dir) / "R3b.json"), Path(a.dir) / "R3b_truth")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
