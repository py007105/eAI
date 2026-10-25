"""Read-only post-mortem skeleton for ONE benchmark run, from its stored row only (no code is touched, no container is called).

    python tools/postmortem_extract.py --arm eternalai_autopilot --scenario crash --seed 100 [--raw PATH]

Answers, in order, what the stored incident log can and cannot say: detected? classified? did policy allow an action? did the executor
run? did verification fail? was evidence preserved, were repeated attempts stopped, did it escalate cleanly? Anything the row does not
contain is printed as "NOT IN THE STORED ROW" with the place where the evidence would be (so the gap is explicit, never guessed).
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--raw", default="docs/results/benchmark_raw.jsonl")
    a = ap.parse_args()
    row = next((json.loads(line) for line in Path(a.raw).read_text().splitlines()
                if (r := json.loads(line))["arm"] == a.arm and r["scenario"] == a.scenario and r["seed"] == a.seed), None)
    if row is None:
        raise SystemExit("no such run in the raw file")
    s = row["score"]
    # The runner fetches the incident list AFTER the run, so it can include incidents opened during the restore that follows the
    # observation window. The scorer only saw those opened before `t_end`; split them so the two are never confused.
    t_end = s.get("t_end")
    incs = [i for i in row["incidents"] if t_end is None or i["opened_t"] <= t_end]
    late = [i for i in row["incidents"] if t_end is not None and i["opened_t"] > t_end]
    first = incs[0] if incs else None
    L = [f"# Post-mortem skeleton: {a.arm} / {a.scenario} / seed {a.seed}", "",
         f"- target `{row['target']}`, fault parameters {row['params']}, finished {row['finished_at']}, system commit `{row['system_commit']}`, "
         f"brain {row['brain_status'].get('brain')} / {row['brain_status'].get('mode')}",
         f"- scorer: detected={s.get('detected')}, recovered={s.get('recovered')}, final status={s.get('final_status')}, "
         f"failed requests {s.get('failed_request_pct')}%, observation window {s.get('window_s')} s", "", "## 1. Was it detected?",
         f"- {'yes' if s.get('detected') else 'no'}; detection time {s.get('time_to_detect_s')} s; incidents opened inside the scoring window: {len(incs)}"
         + (f" (plus {len(late)} opened after the window ended, during the restore: " + ", ".join(f"`{i['id']}` on {i['services'] if 'services' in i else '?'}" for i in late) + ")" if late else ""), "",
         "## 2. Was it classified (and the injected service ranked)?"]
    if first:
        rk = [(x["service"], round(x["score"], 2)) for x in first["ranking"]]
        L += [f"- first incident `{first['id']}`: ranking {rk}; injected service first: {s.get('diagnosis_top1')}",
              f"- likely cause `{first['likely_cause']}`, abstained={first['abstained']}; expected label correct: {s.get('cause_correct')}",
              "- the stored row does NOT contain the model confidence or the reason for an abstention (novelty gate or low confidence); "
              "both are in the preserved evidence file `runtime/evidence/<incident id>.json` in the `eternalai-runtime` volume (field `confidence` and the evidence list)"]
    L += ["", "## 3. Did policy allow the action?"]
    acts = [x for i in incs for x in i["actions"]]
    L += [f"- {x['runbook_id']} on {x['service']}: verdict `{x['verdict']}` ({x.get('reason', '')})" for x in acts] or \
         ["- no action was proposed, so the policy engine was never consulted"]
    L += ["", "## 4. Did the executor run?",
          f"- actions executed: {s.get('actions_executed')} " + ("; " + "; ".join(f"{x['runbook_id']}@{x['service']} executed={x['executed']}" for x in acts) if acts else "")]
    L += ["", "## 5. Did verification fail?"]
    vers = [(i["id"], i["verification"]) for i in incs if i.get("verification")]
    L += [f"- incident {i}: {v['outcome']} ({v['success_rate']:.0%} of {v['probes']} probes)" for i, v in vers] or ["- verification never ran (no action was executed)"]
    L += ["", "## 6. Evidence preserved, repeated attempts stopped, clean escalation?"]
    for i in incs:
        L.append(f"- incident `{i['id']}` status `{i['status']}`" + (f", closed {i['closed_t'] - i['opened_t']:.1f} s after opening" if i['closed_t'] else ", never closed"))
        L += [f"    - +{t['t'] - i['opened_t']:.1f}s {t['msg']}" for t in i["timeline"]]
    L += ["- escalation message in the log: " + str(any("escalated" in t["msg"] for i in incs for t in i["timeline"])),
          "- evidence file on disk: NOT IN THE STORED ROW; verify with a read-only listing of the `eternalai-runtime` volume after the benchmark ends",
          f"- repeated interventions: {s.get('actions_executed')} executed, {s.get('incidents_opened')} incidents opened (more than one incident for one fault is a duplicate alert)",
          "", "## 7. Triage (fill in with evidence; see docs/EVALUATION_PLAN.md section 9)",
          "- class: (a) harness artifact / (b) system bug / (c) design limitation: ____", "- evidence: ____", "- consequence for v2: ____"]
    print("\n".join(L))


if __name__ == "__main__":
    main()
