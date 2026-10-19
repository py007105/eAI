"""Render the live-LLM check (five non-benchmark incidents) from the raw rows, next to the evaluated v2 autopilot behaviour for the same scenarios.

    python scripts/render_llm_live.py --raw results/llm-live/llm_live_raw.jsonl --evaluated results/benchmark-v2/rerun/benchmark_v2_evaluated.jsonl --out docs/results/llm_live.md

Every number is computed here. The live rows are NOT benchmark rows: seeds 2100-2105, a different brain start, LLM key present, run outside the frozen evaluation.
"""
import argparse
import json
from pathlib import Path


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def executed(inc):
    return [f"{a['runbook_id']}@{a['service']}" for a in (inc.get("actions") or []) if a.get("executed")]


def calls(inc):
    """(attempted, ok, kind) for the report call(s) of one incident, from report_meta."""
    m = inc.get("report_meta") or {}
    reasons = m.get("fallback_reasons") or []
    ok = 1 if m.get("provider") not in (None, "template") else 0
    return ok + len(reasons), ok, reasons, m


def render(live, ev, label=""):
    L = [f"# Live LLM check (Step 3), five non-benchmark incidents{label}", "",
         "Seeds 2100-2105 (set A) or 2110-2115 (set B) (outside every benchmark and training range), autopilot, the brain started with the Gemini key from `.env` (key value never printed). "
         "These are not benchmark rows and are not added to any evaluated count. The deterministic decision is made before any LLM call; the LLM only writes the report text. "
         "A comparison with the evaluated v2 autopilot rows is about behaviour, not statistics: n = 5 here and different seeds.", "",
         "## Per incident", "",
         "| scenario | seed | target | provider that answered | LLM latency s | fallback reasons | LLM disagreed | LLM runbook suggestion | executed (deterministic) | verification | seconds to verified recovery | failed-request % |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tot_att = tot_ok = 0
    lat = []
    for r in sorted(live, key=lambda r: r["seed"]):
        for inc in r["incidents"]:
            att, ok, reasons, m = calls(inc)
            tot_att += att
            tot_ok += ok
            if m.get("latency_s") is not None:
                lat.append(m["latency_s"])
            s = r["score"]
            L.append(f"| {r['scenario']} | {r['seed']} | {r['target']} | {m.get('provider')} | {m.get('latency_s', '-')} | {', '.join(reasons) or '-'} | "
                     f"{m.get('llm_disagreed', '-')} | {m.get('llm_runbook_suggestion', '-')} | {', '.join(executed(inc)) or '-'} | "
                     f"{(inc.get('verification') or {}).get('outcome', '-')} | {s.get('time_to_verified_recovery_s', '-')} | {s.get('failed_request_pct')} |")
    L += ["", "## Per call summary", "",
          f"- incidents with a report call: {sum(1 for r in live for _ in r['incidents'])}; calls attempted (answered + failed): {tot_att}; answered and schema-valid: **{tot_ok}/{tot_att}**",
          f"- latency of the report path per incident (seconds; includes failed attempts and the fallback; max is bounded by the per-request timeout of 20 s per provider): "
          f"{', '.join(f'{x:.1f}' for x in sorted(lat)) or '-'}",
          "- 'schema-valid' here means the provider answered and the strict validator accepted it. A timeout is not a schema failure; it is listed under fallback reasons.", "",
          "## Evaluated v2 autopilot behaviour for the same scenarios (valid rows, other seeds, template reports)", "",
          "| scenario | evaluated n | executed runbooks | seconds to verified recovery (values) | live check seconds | same runbook as evaluated |", "|---|---|---|---|---|---|"]
    for sc in sorted({r["scenario"] for r in live}):
        e = [r for r in ev if r["arm"] == "eternalai_autopilot" and r["scenario"] == sc]
        ex = sorted({x for r in e for i in r["incidents"] for x in executed(i)})
        exr = sorted({x.split("@")[0] for x in ex})
        tt = [r["score"].get("time_to_verified_recovery_s") for r in e]
        lv = [r for r in live if r["scenario"] == sc]
        lrb = sorted({x.split("@")[0] for r in lv for i in r["incidents"] for x in executed(i)})
        lt = [r["score"].get("time_to_verified_recovery_s") for r in lv]
        L.append(f"| {sc} | {len(e)} | {', '.join(exr)} | {' '.join(str(t) for t in tt)} | {' '.join(str(t) for t in lt)} | {lrb == exr} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, nargs="+", help="LABEL=path for each set, e.g. 'A (default model)=results/llm-live/set_a.jsonl'")
    ap.add_argument("--evaluated", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ev = rows(a.evaluated)
    t = "\n".join(render(rows(x.split("=", 1)[1]), ev, " - set " + x.split("=", 1)[0]) for x in a.raw)
    Path(a.out).write_text(t, encoding="utf-8")
    print(t)


if __name__ == "__main__":
    main()
