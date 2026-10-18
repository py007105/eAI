# Forecast check: design (not yet run)

Status: **design only, no result exists.** Written while the benchmark runs; run only after the benchmark is finished, exported and checksummed (`docs/EVALUATION_PLAN.md`, Amendments 1 and 2). The v1 benchmark rows do not store forecasts, so early-warning lead time is
"not measured in benchmark v1"; this check is the only place it gets measured. Its results go in `docs/results/forecast_check.md`, never into benchmark tables.

## Question

For a gradual memory leak and a gradual disk fill, does EternalAI issue an exhaustion warning before the resource limit is reached, how much earlier, and does it stay quiet on a healthy traffic surge and a healthy deployment?

## Setup (all fixed here, before any run)

- **Seeds:** 3000-3004 for each scenario. They are disjoint from training (1000+ region used by collection), the benchmark (100-149) and the smoke tests (2000+). Not reused for anything else.
- **Runs:** 5 `memory_leak`, 5 `disk_fill`, 5 `traffic_surge`, 5 `good_deploy` = 20 runs, about 3 minutes each, so roughly 1 hour plus restore waits. Scenario order randomised with a fixed seed.
- **Brain:** `eternalai` in **watch-only** mode, so it can warn and open a predicted incident but never acts. The resource therefore keeps growing and the *actual* time of exhaustion is observed in the same run, with no separate control arm.
  Before the real runs, one smoke run per fault confirms that a predicted incident is opened in watch-only mode (the code path `Engine._predictive` is not mode-gated as far as I read it, but that is an assumption until seen).
- **System under test:** the tag `benchmark-system-v1` code, unchanged; frozen models `models-v1`.

## Double use: live watch-only verification (item 22)

Because the brain runs in **watch-only** mode here, the same 20 runs are also the live check of watch-only mode. It is reported as such, with these extra criteria fixed in advance: in every run `/audit` and the incident rows show **0 executed actions** (no restart, recreate, rollback or cleanup), and at least one incident (predicted or reactive) is opened in each of the 10 leak/disk runs. A single executed action in any run is a watch-only failure, reported as is. This verifies watch-only on this scripted workload only.

## Measurements (computed by a script from raw data, never typed)

1. **First warning time** `t_warn`: `opened_t` of the earliest incident with `kind == "predicted"` (the system's own early-warning event: the engine opens it only when a forecast says exhaustion is closer than `PREDICT_HORIZON_S` = 90 s and the resource is above 25% of its limit), read from `GET /incidents` right after the run. *Amended before any run (2026-10-18):* forecast evidence items attached to reactive incidents (every reactive incident on any service carries one, with whatever ETA the trend gives, e.g. `exhaustion in 254433-497405s`) are **not** warnings; they are counted and reported separately as "forecast evidence on reactive incidents", with their ETA, and never enter lead time or the false-warning count.
2. **Time of exhaustion** `t_limit`, from Prometheus, independent of the brain: first sample where `mem_bytes >= 0.95 * mem_limit_bytes` (memory) or `scratch_bytes >= SCRATCH_LIMIT_BYTES` (disk); if the container is OOM-killed or restarted first, the time of that event is used. A run that never reaches its limit before the scenario timeout has `t_limit` censored and is reported as such.
3. **Lead time** = `t_limit - t_warn` (seconds), per run. Also the first forecast's stated window `[eta_earliest_s, eta_latest_s]` against the actual `t_limit - t_warn`: reported as inside / outside.
4. **False warnings:** any predicted incident or forecast evidence in the `traffic_surge` and `good_deploy` runs, and any warning that names a service other than the injected target in the leak/disk runs.
5. The raw Prometheus series for each run are saved next to the table so the limit time can be rechecked.

## Success criteria (fixed in advance)

Reporting wording: results are stated as counts over the runs actually made, for example "0 warnings in 5 healthy runs" (per healthy scenario), never as "no false warnings", which would claim more than 5 runs can show.

| criterion | pass if |
|---|---|
| warning issued | at least 4 of 5 runs for each of `memory_leak` and `disk_fill` have a warning before `t_limit` |
| lead time | median lead time at least **30 s** for each fault type; every run's lead time listed |
| warnings on healthy runs | **0** warnings in the 5 `traffic_surge` runs and **0** in the 5 `good_deploy` runs (any warning is a fail, reported as is) |
| wrong-service warnings | 0 in the leak/disk runs |

Not a pass/fail criterion, only reported: how often the stated window contained the actual time. With n = 5 per fault, results are reported as raw per-run values and counts, with no confidence claims. A failed criterion is reported as failed and is not
tuned away on these seeds; a fix would be a v2 evaluated on fresh seeds.

## What this check does not show

- Whether acting on the warning prevents the failure (that is recovery, measured by the benchmark arms).
- Any other resource (CPU, file descriptors), sudden faults (crash), or any other application.
- It uses scripted leaks of a fixed growth shape; a leak with a different shape or a very slow rate is untested.

## Procedure (after the benchmark; Docker permission rules apply)

1. Confirm 225/225, no benchmark process, export checksummed.
2. `python scripts/preflight.py`; start the brain in watch-only mode; smoke run one `memory_leak` and one `disk_fill` on seeds 3900 and 3901 (excluded) to confirm the predicted incident appears.
3. Run the 20 runs through the evaluator, saving `/incidents` and the Prometheus ranges per run.
4. Compute the table with a script (to be written and fixture-tested before the run), commit it with the raw files, and report every criterion as pass or fail.
