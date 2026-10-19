"""Fill the generated blocks of the documents from the exported rows, so no v2 number in the prose is typed by hand.

    python scripts/build_docs.py            # rewrite the blocks
    python scripts/build_docs.py --check    # exit 1 if any block is out of date (used by the release check)

Each target document contains `<!-- gen:NAME -->` ... `<!-- /gen:NAME -->`. The text between the markers comes from `docs/_src/NAME.md`, in which `{{key}}`
placeholders are replaced by values computed here from results/benchmark-v1/benchmark_raw.jsonl and results/benchmark-v2/rerun/*. An unknown key is an error.
Text outside the markers is hand-written prose and contains no v2 result numbers.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_v2_report import SUPPORTED, frac, rows, sel, wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"EVALUATION.md": "docs/EVALUATION.md", "README.md": "README.md", "QA_FOR_JUDGES.md": "docs/QA_FOR_JUDGES.md", "DEMO.md": "docs/DEMO.md"}
HEALTHY = ["traffic_surge", "good_deploy"]


def mean(x):
    x = list(x)
    return sum(x) / len(x)


def values():
    d = ROOT / "results/benchmark-v2/rerun"
    ev, rer = rows(d / "benchmark_v2_evaluated.jsonl"), rows(d / "benchmark_v2_rerun_raw.jsonl")
    inv = json.loads((d / "invalid_rows.json").read_text(encoding="utf-8"))
    v1 = rows(ROOT / "results/benchmark-v1/benchmark_raw.jsonl")
    jobs = inv["jobs"]
    fresh = sorted({j["seed"] for j in jobs if j["kind"] == "fresh"})
    V = {"n_eval": len(ev), "n_rerun": len(rer), "n_valid": len(ev) - len(rer), "n_invalid": len(inv["invalid"]), "n_jobs": len(jobs),
         "n_same": sum(j["kind"] == "same-seed" for j in jobs), "n_fresh": sum(j["kind"] == "fresh" for j in jobs),
         "n_fresh_seeds": len(fresh), "fresh_lo": fresh[0], "fresh_hi": fresh[-1]}
    stock = [r["stock"] for r in rer if r.get("stock")]
    V["min_stock"] = min(min(s["after_run"].values()) for s in stock if s.get("after_run"))
    V["n_restocks"] = sum(1 for s in stock if s.get("restocked"))
    for arm, tag in (("eternalai_autopilot", "ap"), ("eternalai_ask_first", "af")):
        f = sel(ev, arm, SUPPORTED)
        V[f"{tag}_det"] = frac(sum(1 for r in f if r["score"].get("detected")), len(f))
        V[f"{tag}_rec"] = frac(sum(1 for r in f if r["score"].get("recovered")), len(f))
        V[f"{tag}_rec_k"] = f"{sum(1 for r in f if r['score'].get('recovered'))}/{len(f)}"
        V[f"{tag}_failed"] = f"{mean(r['score']['failed_request_pct'] for r in f):.2f}"
        V[f"{tag}_detect_s"] = f"{mean(r['score']['time_to_detect_s'] for r in f if r['score'].get('detected')):.2f}"
        V[f"{tag}_n_sup"] = len(f)
    for arm, tag in (("eternalai_autopilot", "ap"), ("threshold_restart", "thr"), ("eternalai_ask_first", "af")):
        h = sel(ev, arm, HEALTHY)
        k = sum(1 for r in h if (r["score"].get("incidents_opened") or 0) > 0)
        a = sum(1 for r in h if (r["score"].get("actions_executed") or 0) > 0)
        V[f"{tag}_hinc"], V[f"{tag}_hinc_k"] = frac(k, len(h)), f"{k}/{len(h)}"
        V[f"{tag}_hact"], V[f"{tag}_hact_k"] = frac(a, len(h)), f"{a}/{len(h)}"
    ts = sel(ev, "eternalai_autopilot", ["traffic_surge"])
    V["ap_surge_inc"] = f"{sum(1 for r in ts if (r['score'].get('incidents_opened') or 0) > 0)}/{len(ts)}"
    u = sel(ev, "eternalai_autopilot", ["cpu_burn"])
    V["cpu_v2"] = f"{sum(1 for r in u if r['score'].get('abstained_correctly'))}/{len(u)}"
    r426 = next(r for r in u if r["seed"] == 426)
    i = r426["incidents"][0]
    rank = [x["service"] for x in i["ranking"]]
    V.update({"s426_seed": r426["seed"], "s426_fail": f"{r426['score']['failed_request_pct']:.2f}", "s426_target": r426["target"], "s426_acted": i["actions"][0]["service"],
              "s426_rank_target": rank.index(r426["target"]) + 1, "s426_novelty": f"{i['diagnosis']['novelty']:.2f}",
              "s426_thr": f"{i['diagnosis']['novelty_threshold']:.2f}", "s426_probes": f"{round(i['verification']['success_rate'] * i['verification']['probes'])}/{i['verification']['probes']}",
              "s426_conf": f"{i['confidence']:.2f}"})
    f1 = [r for r in v1 if r["arm"] == "eternalai_autopilot" and r["scenario"] in SUPPORTED]
    h1 = [r for r in v1 if r["arm"] == "eternalai_autopilot" and r["scenario"] in HEALTHY]
    u1 = [r for r in v1 if r["arm"] == "eternalai_autopilot" and r["scenario"] == "cpu_burn"]
    V.update({"v1_ap_rec": f"{sum(1 for r in f1 if r['score'].get('recovered'))}/{len(f1)}", "v1_ap_failed": f"{mean(r['score']['failed_request_pct'] for r in f1):.2f}",
              "v1_ap_detect_s": f"{mean(r['score']['time_to_detect_s'] for r in f1 if r['score'].get('detected')):.1f}",
              "v1_ap_hfalse": f"{sum(1 for r in h1 if (r['score'].get('false_alerts') or 0) > 0)}/{len(h1)}",
              "v1_cpu": f"{sum(1 for r in u1 if r['score'].get('abstained_correctly'))}/{len(u1)}",
              "v1_na_failed": f"{mean(r['score']['failed_request_pct'] for r in v1 if r['arm'] == 'no_action' and r['scenario'] in SUPPORTED):.2f}"})
    V["v2_det_s_ap_short"] = f"{mean(r['score']['time_to_detect_s'] for r in sel(ev, 'eternalai_autopilot', SUPPORTED) if r['score'].get('detected')):.1f}"
    for tag, fn in (("a", "set_a_default_model"), ("b", "set_b_gemini-3.5-flash-lite")):
        lp = ROOT / f"results/llm-live/{fn}.jsonl"
        if not lp.exists():
            continue
        ms = [i.get("report_meta") or {} for r in rows(lp) for i in r["incidents"]]
        ok = [m for m in ms if m.get("provider") not in (None, "template")]
        rs = [x for m in ms for x in (m.get("fallback_reasons") or [])]
        V[f"llm_{tag}_valid"] = f"{len(ok)}/{len(ms)}"
        V[f"llm_{tag}_timeouts"] = sum("ReadTimeout" in x for x in rs)
        V[f"llm_{tag}_other_fail"] = sum("ReadTimeout" not in x for x in rs)
        V[f"llm_{tag}_lat_ok"] = (f"{min(m['latency_s'] for m in ok):.1f}-{max(m['latency_s'] for m in ok):.1f}" if ok else "-")
        V[f"llm_{tag}_rec"] = f"{sum(1 for r in rows(lp) if r['score'].get('recovered'))}/{len(rows(lp))}"
        V[f"llm_{tag}_ttvr"] = f"{min(r['score']['time_to_verified_recovery_s'] for r in rows(lp)):.1f}-{max(r['score']['time_to_verified_recovery_s'] for r in rows(lp)):.1f}"
        V[f"llm_{tag}_same_rb"] = f"{sum(1 for r in rows(lp) for i in r['incidents'] if (i.get('report_meta') or {}).get('llm_disagreed') is False)}/{len(ms)}"
    fr = [r for r in ev if r["scenario"] in SUPPORTED and r["arm"] in ("eternalai_autopilot", "eternalai_ask_first")]
    mi = [r for r in fr if (r["score"].get("incidents_opened") or 0) > 1]
    ma = [r for r in fr if (r["score"].get("actions_executed") or 0) > 1]
    V.update({"multi_inc": len(mi), "multi_act": len(ma), "n_fault_runs": len(fr),
              "multi_scen": ", ".join(sorted({f"{r['scenario']} seed {r['seed']} ({r['arm'].replace('eternalai_', '')})" for r in mi + ma}))})
    crit = (ROOT / "docs/results/v2_criteria_final.md").read_text(encoding="utf-8").splitlines()
    V["criteria_table"] = "\n".join(l for l in crit if l.startswith("|"))
    V["wilson_lo_18"] = f"{wilson(18, 18)[0] * 100:.0f}"
    V["wilson_hi_1_24"] = f"{wilson(1, 24)[1] * 100:.0f}"
    V["wilson_lo_3"] = f"{wilson(3, 3)[0] * 100:.0f}"
    return V


def fill(text, V, name):
    def sub(m):
        if m.group(1) not in V:
            raise KeyError(f"{name}: unknown placeholder {{{{{m.group(1)}}}}}")
        return str(V[m.group(1)])
    return re.sub(r"\{\{([a-z0-9_]+)\}\}", sub, text)


def build(check):
    V = values()
    bad = []
    for fname, rel in TARGETS.items():
        p = ROOT / rel
        t = p.read_text(encoding="utf-8")
        new = t
        for m in list(re.finditer(r"<!-- gen:([a-z0-9_]+) -->.*?<!-- /gen:\1 -->", t, re.S)):
            name = m.group(1)
            body = fill((ROOT / f"docs/_src/{name}.md").read_text(encoding="utf-8").strip("\n"), V, name)
            new = new.replace(m.group(0), f"<!-- gen:{name} -->\n{body}\n<!-- /gen:{name} -->")
        if new != t:
            bad.append(rel)
            if not check:
                p.write_text(new, encoding="utf-8")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    bad = build(a.check)
    if a.check:
        print("out of date: " + ", ".join(bad) if bad else "all generated blocks are current")
        sys.exit(1 if bad else 0)
    print("updated: " + (", ".join(bad) if bad else "nothing (already current)"))


if __name__ == "__main__":
    main()
