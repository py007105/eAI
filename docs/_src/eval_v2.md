## Canonical methodology, results and limitations: benchmark v2 (final)

This section is the single place where the v2 caveats are written out in full. The README, the demo script and the judge Q&A refer here instead of repeating them. Every number below is filled in by `tools/build_docs.py` from the exported rows (`results/benchmark-v2/rerun/`); the full tables are in `docs/results/benchmark_v2.md` (rendered by `tools/render_v2_report.py`) and `docs/results/benchmark_v1_v2.md` (side by side). Nothing here is typed by hand.

### What v2 is, and the wording rule (Amendment 6)

v2 is **fixes for the failures v1 exposed, tested on fresh seeds**. It is not evidence that "the model is better". v2 differs from v1 in four things that changed together: the retrained models (72 original + 34 fresh training runs), the memory features (relative growth instead of absolute levels), the approval-queue fix (time-to-live, non-blocking pending approvals, a real benchmark token) and the telemetry condition (T3: trace exporter off, no collector). **No improvement or change is attributable to any single one of them.** v1 and v2 are **unpaired** (v1 seeds 100-148, v2 seeds 200-318 plus the replacement block 400-429) and v2 is a **reduced plan** (Amendment 4 section M): three autopilot, three ask-first and no baseline run per supported fault, twelve autopilot and twelve threshold_restart and four ask-first runs per healthy scenario. Any statement about telemetry is a HYPOTHESIS unless a controlled test exists (`docs/postmortems/telemetry-conditions-by-batch.md`).

### Run accounting, exclusions and replacement runs (Amendment 8)

- Evaluated set: **{{n_eval}}** rows = **{{n_valid}} valid original rows + {{n_rerun}} replacement rows**.
- During Stage 3 the inventory service ran out of stock (it only subtracts stock; there is no add-stock endpoint). It was first noticed from the result pattern (every verification probe answered HTTP 409) and then confirmed against stock records. **{{n_invalid}} original rows** whose run ended after the last confirmed in-stock checkout (23:30:36 IST on 2026-10-18) were marked invalid by a timestamp rule fixed before any row was classified, applied mechanically (also to rows that looked clean). They stay in `benchmark_v2_raw.jsonl` and in `invalid_rows.json`; none was deleted.
- **The replacement runs were designed after the problem was discovered.** The rule was committed before any restock or re-run and uses stock timestamps, not outcomes, but a reader should know the sequence. Of the {{n_jobs}} replacement runs, **{{n_same}} reused the original seed** (the partner arm's row was valid, so pairing was kept) and **{{n_fresh}} used fresh seeds** from a block pre-checked for overlap ({{n_fresh_seeds}} distinct seeds, {{fresh_lo}}-{{fresh_hi}}).
- Replacement runs ran behind a **stock gate** (harness tooling, direct SQL restock because adding an endpoint would be a system change, verified through `GET /items`; {{n_restocks}} restock was needed; lowest stock after any replacement run: {{min_stock}}). The gate and the per-run stock record exist **only for the replacement runs**. The original valid rows had neither.
- Other harness differences, stated: replacement runs were one `run_benchmark.py` invocation each, in ascending seed order, and the `rep` field is 0; one run (disk_fill seed 204, evaluator run 8e932d23e9) finished after a driver crash and has no row (excluded; it is still in the evaluator export); the original Stage 3 had one memory kill and one automatic resume. Telemetry condition T3, the models, the arms and the scoring were unchanged.
- **Stock evidence:** a log-proven timeline exists for **one SKU only** (`sku-mug`, the verification probe's SKU). The other three SKUs are supported by indirect observations only (similar consumption, the load generator's random SKU choice, and the service seeding the same level for each; no inventory logs survive). The 72 original training runs, the 34 fresh runs and the v1 benchmark were checked for a stock-out signature **without finding one**; that is absence of evidence in the records that exist (`docs/results/stock_validity.md`).

### Pre-registered criteria (Amendment 4 section N) and what was observed

{{criteria_table}}

All seven passed, so by the pre-registered rule P the demo may show v2. **Passing criteria written with a reduced sample is not a measurement of reliability.** How much certainty the counts carry (Wilson 95% intervals, treating runs as independent, which flatters them):

- Supported faults, autopilot: **{{ap_det}} detected, {{ap_rec}} recovered** by its own verification. With 18 runs, a perfect count is still consistent with a true success rate as low as about {{wilson_lo_18}}%. Each fault type has n = 3 (a perfect 3/3 is consistent with a rate as low as {{wilson_lo_3}}%), so no per-fault claim is made.
- Healthy runs, autopilot: **{{ap_hinc}}** opened an incident and **{{ap_hact}}** executed an action. One incident in 24 is consistent with a true rate anywhere up to about {{wilson_hi_1_24}}%. The one incident was in a traffic surge ({{ap_surge_inc}} surge runs opened one). The same-seed threshold_restart baseline opened {{thr_hinc}}; ask-first opened {{af_hinc}} with {{af_hact}} actions.
- Ask-first: {{af_det}} detected and {{af_rec}} recovered, zero approval failures (v1's ask-first arm was invalid, see the postmortem, so there is no valid v1 comparison).
- Mean failed-request % over the 18 supported autopilot runs: {{ap_failed}}; mean detection {{ap_detect_s}} s. For reference, v1 autopilot (different seeds) was {{v1_ap_failed}}% and {{v1_ap_detect_s}} s; the v1 no-action arm was {{v1_na_failed}}%. **The detection times are a tie within noise; the failed-request figures are not comparable** (different seeds, fault targets and conditions).

### How recovery is judged (and what that does not prove)

**Recovery is verified internally**: the brain's own synthetic checkout through web, orders, inventory and payments over a window. The **failed-request %** is an independently measured **impact metric** (the evaluator reads the load generator's counters), but it is not complete independent proof of recovery: no `no_action` arm exists in v2 to give a same-seed reference, there are no independent probe logs, and a low failed-request % can also occur when a fault never hurt the user path (disk_fill rows show 0.0%). Treat "recovered" as "the system's own check passed", supported but not proven by the impact metric.

### Baseline comparisons

There is **no paired v2 baseline comparison for supported faults** (only autopilot and ask-first ran on them), so nothing here claims EternalAI is better than a restart-on-threshold script at recovering faults. The only same-seed baseline in v2 is `threshold_restart` on healthy runs ({{thr_hinc}} incidents against {{ap_hinc}} for the autopilot, same seeds). v1's baseline comparison (no_action, threshold_restart, prototype_rules) is on different seeds and an older system version; it is unpaired with v2, and in v1 the autopilot was not ahead on several metrics (listed above). Extension B (an autopilot / threshold_restart / no_action comparison on the supported faults, planned as Amendment 9) was **skipped by the pre-set rule**: it needs at least 10 hours before the system freeze, and on 2026-10-19 at 15:11 IST there were about 8 hours before the freeze at 23:10 IST (the sample sizes, the run time and the margin needed for rehearsals and release checks did not fit).

### Unseen fault: cpu_burn (no runbook, never in training)

- v2: the autopilot **abstained in {{cpu_v2}}** runs; v1: it abstained in **{{v1_cpu}}**. These are different versions on different seeds and are **not pooled into one rate**. Neither supports a claim that EternalAI "abstains on unseen faults" or "knows when to stop".
- **Seed 426 (v2) is a failure.** The injected fault was on `{{s426_target}}`. The ranker put `{{s426_target}}` **{{s426_rank_target}}rd**, the novelty score ({{s426_novelty}}) was below the abstention threshold ({{s426_thr}}) and the class confidence ({{s426_conf}}) was above the abstain limit, so the autopilot restarted `{{s426_acted}}`, a service that was not the target. Failed requests were {{s426_fail}}% and the verification checkouts were {{s426_probes}} (ReadTimeout). The scorer flags this as "harmful" only by its definition (an executed action on a service other than the injected target); **whether the restart added damage is unknown** (no unrestarted control for that seed, and Prometheus no longer holds the window). Conclusion, accepted: a **model generalisation limitation**; an implementation defect is not evidenced but not ruled out. **Decision: not fixed before the freeze** (a fix would be v3 on fresh seeds). Full timeline: `docs/postmortems/cpu_burn_seed426.md`.

### Training data and telemetry conditions

The retrained models were trained on **two telemetry conditions**: the 72 original runs with the trace exporter on (collector state during that period was not recorded) and the 34 fresh runs with it off (T3). The condition is not a model input and cross-validation folds mix both, so cross-validation cannot separate its effect. v1's benchmark ran with the exporter on and the collector dead; v2 ran under T3. **HYPOTHESIS, not a finding:** that the dead collector explains the v1 memory shift (`docs/postmortems/telemetry-conditions-by-batch.md`); the supporting Stage 0 diagnostic had two runs per condition.

### Health-log coverage

An external container health log (`tools/health_watch.py`, once a minute, read-only) exists only from 2026-10-19 00:29:31 IST. Original valid rows that ran before then, including the P1 runs and the first ask-first fault runs, are **not covered** by it, so a container fault outside the brain's own record could not be excluded for those runs. All {{n_rerun}} replacement runs are covered. A once-a-minute sampler can miss a short restart; seven replacement rows show a single-sample "exited" state explained by the injected crash or the brain's start.

### What remains undemonstrated

- **Forecast lead time**: The pre-registered 20-run live forecast check (v3, `docs/results/forecast_check.md`) FAILED its memory-lead criterion (median lead 18.3 s against the 30 s target, warned in 5 of 5 runs) and passed for a gradual disk fill (median lead 86.4 s, 5 of 5), with 0 warnings in 10 healthy runs; its stated time-to-limit window held the actual time in 0 of 10 runs.
- **Groq** was never tested (no key was available).
- **Gemini**: see the LLM paragraph in section 5 (Limitations) for the tests actually performed; the benchmark brains ran without LLM keys, so the LLM did not contribute to any benchmark number.
- **Other applications**: nothing was tested on another application.

### Deviations, exclusions and amendments, in order

Amendment 4 (reduced v2 plan, pass criteria, demo rule P, triage classes) · Amendment 5 (Stage 1 record, longer gap between runs) · Amendment 6 (this wording rule) · Amendment 7 (external health log, 2026-10-19 00:29 IST) · Amendment 8 (stock-out, exclusion rule, direct-SQL restock as a harness action, replacement plan). All are in `docs/EVALUATION_PLAN.md`. The criteria were not changed after any result was read. Original files are kept, replacements are in their own files, and the evaluated set is a derived file (`tools/v2_combine.py`) that can be rebuilt; checksums: `results/benchmark-v2/SHA256SUMS` and `SHA256SUMS-rerun`.
