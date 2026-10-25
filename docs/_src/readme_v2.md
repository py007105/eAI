## Benchmark v2 (final): fixes for the failures v1 exposed, tested on fresh seeds

v1 results above are kept unchanged. v2 is **not** presented as "the model is better": four things changed together (retrained models, memory features, approval-queue fix, telemetry condition T3), v1 and v2 are unpaired on different seeds, and v2 is a reduced plan. All caveats, exclusions and amendments are in one place: **`docs/EVALUATION.md`, section "Canonical methodology, results and limitations: benchmark v2"**. Tables: `docs/results/benchmark_v2.md`, `docs/results/benchmark_v1_v2.md`.

| v2 (seeds 200-318 and the replacement block 400-429) | observed | certainty |
|---|---|---|
| supported faults, autopilot: detected / recovered (own verification; v2 benchmark, old policy; current unattended v3: 10/30 recovered alone) | {{ap_det}} / {{ap_rec}} | 18 runs, 3 per fault type; Wilson 95% interval lower bound about {{wilson_lo_18}}% |
| supported faults, ask-first (approvals by a simulated operator after 5 s (no person reviewed); v2 benchmark, old policy): detected / recovered | {{af_det}} / {{af_rec}} | same sample sizes |
| healthy runs, autopilot: incidents opened / actions executed | {{ap_hinc_k}} / {{ap_hact_k}} | upper bound of the interval for 1 in 24 is about {{wilson_hi_1_24}}% |
| healthy runs, threshold_restart on the same seeds: incidents opened | {{thr_hinc_k}} | |
| unseen fault cpu_burn, autopilot: abstained | {{cpu_v2}} (v1: {{v1_cpu}}, other seeds, not pooled) | seed 426 restarted the wrong service (post-mortem in `docs/postmortems/cpu_burn_seed426.md`) |
| mean failed-request %, 18 supported autopilot runs | {{ap_failed}} | independent impact metric, no same-seed no-action reference in v2 |

The evaluated set has {{n_eval}} rows: {{n_valid}} valid original rows and {{n_rerun}} replacement rows run after the inventory stock ran out (the replacement runs were designed after the problem was seen; {{n_same}} reused seeds, {{n_fresh}} used fresh seeds). There is **no paired v2 baseline comparison for supported faults**, the forecast's memory-lead check FAILED (median 18.3 s vs 30 s; disk passed, median 86.4 s) and Groq is untested.
