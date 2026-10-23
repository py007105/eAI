# EternalAI: project snapshot (current state of this repository)

Written 2026-10-20, 20:10 IST, read-only, from the working tree at the commit below. Every claim cites `path:line` or a results file. "not present" means the item does not exist in this repository. Line numbers refer to commit `c587d20`.

---

## 1. Summary

- EternalAI watches a four-service demo shop (web, orders, payments, inventory) running in Docker Compose, reads its Prometheus metrics and Docker container state every 2 s (`eternalai/engine.py:450`, `telemetry/prometheus.yml:2`), and opens an incident when a service stays anomalous for 3 consecutive ticks (`eternalai/engine.py:76`).
- For an incident it ranks the likely root-cause service with a trained gradient-boosted ranker (`eternalai/rca.py:44`), classifies the fault into one of 6 fault classes or "healthy" with a calibrated classifier, and abstains ("insufficient_evidence") when a novelty gate or low confidence says so (`eternalai/classify.py:47-57`).
- It maps the diagnosis to one of four Docker runbooks through a fixed table (`eternalai/classify.py:19-26`); a deterministic policy decides whether the runbook runs, needs human approval, or is blocked (`eternalai/policy.py:41-59`).
- After an executed action it runs a synthetic checkout every second for 20 s and marks the incident recovered only if every checkout succeeds within 1 s (`eternalai/verify.py:31-46`, `eternalai/config.py:29`).
- An LLM (Gemini, then Groq) may rewrite the report text; it cannot choose or run actions (`eternalai/llm.py:116-147`, `eternalai/engine.py:316-333`).
- A separate evaluator container injects 9 scripted scenarios, keeps the ground truth in a volume the brain does not mount, and scores runs (`evaluator/scenarios.py:16-26`, `docker-compose.yml:59`, `docker-compose.yml:75`).
- Not present: Kubernetes support, scaling, notifications, a persistent incident database, retraining.
- Version: branch `release-candidate`, commit `c587d207c6d844c4b2ba3ec1b0db1a3f78fb46b8` (2026-10-20 02:42 +0530), described as `v1.0.0-rc.2-16-gc587d20`. Tags in the repository: `benchmark-system-v1`, `benchmark-system-v2`, `models-v1`, `models-v2`, `v1.0.0-rc.1`, `v1.0.0-rc.2`. No `v1.0.0` tag.

---

## 2. Repository map

Excluded: `.venv`, `__pycache__`, `.pytest_cache`, rehearsal capture folders. `git ls-files` counts 496 tracked files, 167 of them under `results/`.

```
.
├── README.md                      overview, v1 findings, v2 summary (generated block), quick start
├── LICENSE, NOTICE                MIT licence; attributions
├── .env.example                   template: GEMINI_API_KEY, GROQ_API_KEY, ETERNALAI_MODE, ETERNALAI_APPROVAL_TOKEN
├── .env                           git-ignored local secrets (not read for this snapshot)
├── .gitignore, .gitattributes, .dockerignore, pytest.ini
├── docker-compose.yml             the stack: 4 app services, release images, evaluator, eternalai, dashboard, loadgen, prometheus, jaeger
├── docker-compose.llm.yml         tooling override: forwards GEMINI_MODEL to the eternalai service
├── app/                           the demo shop (FastAPI)
│   ├── Dockerfile, requirements.txt
│   ├── common/obs.py              shared metrics, /healthz, /metrics, token-protected /_chaos fault hooks
│   ├── web/main.py                entry service: /, /api/products, /api/checkout
│   ├── orders/main.py             /orders, /orders/{oid}; calls inventory and payments; SQLite
│   ├── payments/main.py           /charge; SQLite
│   └── inventory/main.py          /items, /reserve; SQLite stock
├── loadgen/loadgen.py, Dockerfile continuous browse + checkout traffic (BASE_RPS 6), optional surges
├── telemetry/prometheus.yml       2 s scrape of the 4 services and loadgen
├── eternalai/                     the brain
│   ├── api.py                     FastAPI REST API (port 8000)
│   ├── engine.py                  the loop: observe, detect, diagnose, propose, act, verify, expire
│   ├── collector.py               Prometheus queries and Docker container state
│   ├── features/window.py         rolling-window features shared by training and live use
│   ├── detect.py                  per-service IsolationForest + learned healthy limits; persistence
│   ├── forecast.py                Theil-Sen exhaustion forecast
│   ├── rca.py                     root-cause evidence table, trained ranker, baseline rules
│   ├── classify.py                calibrated fault classifier, abstain logic, cause->runbook table
│   ├── novelty.py                 kNN novelty gate for the abstain decision
│   ├── calibrate.py               temperature scaling
│   ├── safe_model.py              gradient boosting tolerant of constant/empty columns
│   ├── policy.py                  modes, risk table, cooldown, circuit breaker
│   ├── executor.py                Docker SDK runbooks; audit log
│   ├── verify.py                  synthetic-checkout verification
│   ├── investigate.py             evidence items; text retrieval over past verified incidents
│   ├── llm.py                     Gemini / Groq / template report with validation
│   ├── dedupe.py                  release grace and post-incident suppression
│   ├── baselines.py               benchmark baseline brains (threshold_restart, prototype_rules)
│   ├── artifacts.py               save/load model files with metadata
│   ├── evaluation/splits.py       leakage-safe grouped splits
│   ├── config.py                  constants and environment overrides
│   └── Dockerfile, requirements.txt
├── evaluator/                     independent fault injector and scorer (port 8200)
│   ├── main.py                    /runs, /runs/{id}/status, /runs/{id}/reveal, /scorecard
│   ├── scenarios.py               the 9 scenarios, injection and restore
│   ├── scoring.py                 per-run scoring and aggregation
│   └── timing.py                  settle wait before injection (45 s / 200 s)
├── dashboard/                     Dash UI (port 8050)
│   ├── app.py                     layout, callbacks, poller, approval/mode/demo actions
│   ├── views.py                   rendering functions (status line, countdown, panels)
│   ├── demo.py                    Demo mode: start/follow/reveal evaluator runs
│   ├── labels.py                  all UI text, English and Hindi
│   ├── theme.py, assets/style.css styling
│   └── Dockerfile, requirements.txt
├── models/
│   ├── artifacts/                 detectors, classifier, ranker, baselines (.joblib + .json metadata)
│   ├── collect_runs.py            collect labelled live runs through the evaluator
│   ├── check_runs.py              sanity check of collected runs
│   ├── train_models.py            train and cross-validate detector, classifier, ranker
│   ├── eval_rcaeval.py            fault-type experiments on RCAEval RE1
│   ├── eval_transfer.py           leave-one-system-out experiments on RCAEval RE1
│   └── envinfo.py                 environment header for results files
├── data/                          scripts only; no data files are tracked
│   ├── clean_workbook.py          split an external training workbook into tables (workbook not present)
│   ├── download_rcaeval.py        download RCAEval RE1 from Zenodo
│   ├── rcaeval_loader.py          load RCAEval cases into the shared signal schema
│   ├── build_rcaeval_features.py  RCAEval cases -> feature rows
│   └── label_map.py               workbook label -> runtime label mapping
├── scripts/                       about 75 tooling scripts (benchmark drivers, renderers, rehearsal tools, launchers,
│                                  debug helpers); one-line purposes are in each file's first line. Key ones:
│                                  demo.ps1 (launcher), preflight.py, demo_challenge.py, approval_capture.py,
│                                  run_benchmark.py, render_results.py, render_v2_report.py, build_docs.py
├── tests/                         40 test files, 233 test functions (section 19)
├── docs/
│   ├── ARCHITECTURE.md, DATA.md, DATA_QUALITY.md, EVALUATION.md (canonical v2 section), EVALUATION_PLAN.md
│   │   (pre-registered rules and amendments), DEMO.md, QA_FOR_JUDGES.md, MODEL_CARD.md, MODEL_CARD_v1.md,
│   │   FORECAST_CHECK.md, GAP_ANALYSIS.md, POST_BENCHMARK_RUNBOOK.md, REFERENCES.md, V2_PROPOSAL.md, v2_seed_plan.*
│   ├── results/                   33 generated result files (benchmarks, CV, RCAEval, rehearsals, LLM checks)
│   ├── postmortems/               16 post-mortems and triage files
│   ├── _src/                      sources for generated document blocks
│   ├── drafts/v2_docs_skeleton.md placeholder skeleton
│   └── screenshots/               69 images (dashboard states, rehearsal screenshots)
└── results/                       raw evidence: benchmark-v1 (761K), benchmark-v2 (1.5M, with SHA256SUMS),
                                   llm-live, stage0, stage1, surge-capture, forecast-check, rehearsals (37M incl.
                                   captures), demo-export (git-ignored)
```

---

## 3. How to run

- **Generic (README.md:18-23):**
  ```
  git clone https://github.com/py007105/eAI && cd eAI
  cp .env.example .env
  docker compose --profile releases build
  docker compose up -d
  ```
- **Variables in `.env.example`:** `GEMINI_API_KEY` (optional), `GROQ_API_KEY` (optional), `ETERNALAI_MODE` (default `ask-first`), `ETERNALAI_APPROVAL_TOKEN` (placeholder `change-me`; the approve/reject/mode endpoints are refused until it is changed, `eternalai/api.py:51-56`). Optional: `GEMINI_MODEL` via `docker-compose.llm.yml`; `CHAOS_TOKEN` (default `evaluator-only`, `docker-compose.yml:10`).
- **Rehearsed launcher (Windows),** from `docs/DEMO.md` section 0:
  `powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -ConfirmReset -ExportDir results/demo-export/live`.
  It exports and checksums the scorecard, resets the scorecard volume, builds the dashboard, starts the stack under telemetry condition T3 (no Jaeger), restocks inventory and runs `scripts/preflight.py` (8 checks). The file header still says "WRITTEN, NOT YET RUN" (`scripts/demo.ps1:1`); that line is stale, because the launcher was used in rehearsals R1-R5 (`docs/results/demo_rehearsals.md`). `scripts/demo.sh` has the same header and no record of being run.
- **What starts** (`docker-compose.yml`):

  | container | published port | bind | purpose |
  |---|---|---|---|
  | web | 8080 -> 8000 (`:36`) | all interfaces | shop entry |
  | orders, payments, inventory | none | - | shop services |
  | eternalai | 8000 (`:73`) | all interfaces | brain API |
  | evaluator | 8200 (`:58`) | all interfaces | fault injection and scoring |
  | dashboard | 8050 (`:91`) | all interfaces | UI |
  | prometheus | 9090 (`:112`) | all interfaces | metrics |
  | jaeger | 16686 (`:120`) | all interfaces | traces (not started by the demo launcher, condition T3) |
  | loadgen | none | - | traffic |

- **URLs:**
  - dashboard: http://localhost:8050
  - API: http://localhost:8000
  - shop: http://localhost:8080
  - evaluator: http://localhost:8200
  - Prometheus: http://localhost:9090
- **Stop:** `docker compose -p eai stop` (keeps volumes).

---

## 4. Architecture

```
loadgen ──HTTP──> web ──> orders ──> payments
                    └──────> inventory <──┘           (app/, FastAPI; each exposes /metrics, /healthz, /_chaos)
      │ metrics (2 s scrape)
      v
  Prometheus ──PromQL──> eternalai (brain, :8000) <──Docker SDK (socket)──> app containers
                             │ REST
                             v
                         dashboard (:8050) ──REST──> evaluator (:8200) ──Docker SDK + /_chaos──> app containers
                                                        └── truth volume (not mounted by the brain)
  eternalai ──HTTPS (optional)──> Gemini / Groq
```

The loop (`eternalai/engine.py`) runs one `tick()` every 2 s (`:450-457`):

| # | step | input | processing | output |
|---|---|---|---|---|
| 1 | Observe | Prometheus range queries for the last 150 s per service (`:106`); Docker state (`:102`) | `window_features` over the last 10 s (`features/window.py:53`; window from `models/artifacts/classifier.json` `window_s` 10.0) | feature dict per service |
| 2 | Detect | features | `service_anomalous`: not-scraped rule OR forest score > threshold OR any learned limit exceeded (`detect.py:51-52`, `:97-100`); release grace masks a service and its callers (`engine.py:120-126`) | anomalous flag per service |
| 3 | Confirm | flags | `Persistence(3)`: 3 consecutive anomalous ticks (`engine.py:76`, `:170`); suppression after a closed incident (`dedupe.py:42-59`) | confirmed services |
| 4 | Open | confirmed services | new incident only if no incident is open/executing/verifying and more than 8 s since the last close (`engine.py:189-195`) | incident |
| 5 | Diagnose | features, scores, dependency-failure rates | after `max(4, window_s - 4)` s (`engine.py:200`): ranker -> root (`:275-280`); evidence collection (`:281-285`); classifier + novelty gate (`:288-291`); OOM-killed overrides to memory_leak (`:295-296`); "healthy" becomes abstain (`:297-298`) | ranking, label, confidence, abstained, evidence |
| 6 | Report | diagnosis context | template report immediately (`:309`); LLM rewrite in a background thread (`:316-333`) | report text |
| 7 | Propose | label | abstain -> escalate (`:336-340`); else `CAUSE_RUNBOOKS[label][0]` -> `policy.evaluate` (`:341-354`) | execute / needs_approval / observe_only / blocked |
| 8 | Act | approved or autopilot action | `executor.run` in a thread (`:376-392`) | audited container action |
| 9 | Verify | - | wait 3 s, then 20 synthetic checkouts at 1 s (`:394-399`) | recovered / partially_recovered / unresolved |
| 10 | Expire | pending proposals | escalate after 120 s without approval (`:228-244`) | escalated incident |
| 11 | Predict | features (only when no incident is open, `:202-203`) | forecast; if earliest exhaustion < 90 s and usage > 25% of limit, open a "predicted" incident and propose (`:419-447`) | predicted incident |

---

## 5. Telemetry

- **Scrape:** Prometheus every 2 s (`telemetry/prometheus.yml:2`), jobs `app` (4 services) and `loadgen` (`:4-14`). Range-query step 2 s (`eternalai/config.py:15`). Window per tick: 150 s (`eternalai/engine.py:106`).
- **PromQL per service** (`eternalai/collector.py:18-31`, copied verbatim; `{s}` is the service name):
  ```
  req_rate        sum(rate(http_requests_total{service="{s}"}[10s]))
  err_rate        sum(rate(http_requests_total{service="{s}",status=~"5.."}[10s]))
  p95_s           histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="{s}"}[10s])))
  mem_bytes       app_memory_bytes{service="{s}"}
  mem_limit_bytes app_memory_limit_bytes{service="{s}"}
  cpu_cores       rate(process_cpu_seconds_total{instance_name="{s}"}[10s])
  up              up{job="app",instance_name="{s}"}
  dep_fail_rate   sum(rate(dependency_calls_total{service="{s}",outcome="error"}[10s]))
  error_log_rate  rate(error_logs_total{service="{s}"}[10s])
  restarts_3m     changes(app_start_time_seconds{service="{s}"}[3m])
  deploys_3m      changes(app_release_seq{service="{s}"}[3m])
  scratch_bytes   app_scratch_disk_bytes{service="{s}"}
  ```
- **Per caller/callee pair** (`collector.py:57-60`):
  `sum(rate(dependency_calls_total{service="<caller>",target="<callee>",outcome="error"}[10s]))`.
- **App-wide snapshot** (`engine.py:140-142`):
  - `sum(rate(http_requests_total{service="web"}[10s]))`
  - `sum(rate(http_requests_total{service="web",status=~"5.."}[10s]))`
  - `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="web"}[10s])))`
- **Dependency failures at diagnosis** (`engine.py:152-160`): the same pair query as instant queries.
- **Query volume:** about 12 range queries plus 0-2 pair queries per service per tick, i.e. about 52-56 range queries every 2 s. No error handling inside `Prom.instant`/`Prom.range` (`collector.py:38-49`). A failed query raises and the whole tick is lost; `run_forever` stores the error in `last_error` (`engine.py:450-457`).
- **Docker state** (`collector.py:98-110`): running flag, status, exit code, OOMKilled, image tag, `eai.release_seq` label, StartedAt, container id. Change events are recorded in memory: deploy, restart, stopped (`collector.py:112-127`). Container logs (last 40 lines) are read at diagnosis (`investigate.py:77-94`).

---

## 6. Detection

- **Algorithm:** one detector per service. An IsolationForest (`n_estimators=200`, `max_samples=min(256, n)`, `contamination="auto"`, `detect.py:85`) plus learned healthy-range limits per feature (`detect.py:58-71`). A service is anomalous if it is not scraped/running, OR the forest score exceeds its threshold, OR any limit is exceeded (`detect.py:51-52`, `:97-100`).
- **Features** (`detect.py:21-22`): `lat_ratio, cpu_per_req_ratio, error_ratio, dep_fail_rate, error_log_rate, mem_rel_growth, mem_slope_share_per_min, scratch_mb, scratch_slope_mb_per_min, up_frac`. Upper-only limits on all except `cpu_per_req_ratio`, which is two-sided (`detect.py:24-26`).
- **Thresholds in the saved model** (read from `models/artifacts/detectors.joblib`):

  | service | forest threshold | error_ratio limit (lo, hi) | lat_ratio limit (lo, hi) |
  |---|---|---|---|
  | web | 0.8432 | (-0.004, 0.084) | (-0.351, 2.824) |
  | orders | 0.7112 | (-0.001, 0.063) | (-0.029, 4.091) |
  | inventory | 0.7124 | (-0.0, 0.0) | (-2.324, 7.458) |
  | payments | 0.6572 | (-0.0, 0.0) | (-0.763, 15.026) |

  For inventory and payments the upper limits of `error_ratio`, `dep_fail_rate` and `error_log_rate` round to 0.0, so any non-zero value exceeds them.
- **How thresholds were chosen:** forest threshold = largest healthy validation score + 0.05 (`detect.py:75`, `:92-93`); limit margin 1.0 healthy spreads (`detect.py:74`). Both were chosen by grouped cross-validation (`docs/results/detector_margin.md`). The same document and `docs/results/models_cv_v2.md` state the forest "turned out to add nothing measurable over the limits".
- **Persistence and hygiene:**
  - 3 consecutive ticks (`engine.py:76`);
  - release grace 15 s (`config.py:30`, `dedupe.py:29-40`);
  - quiet period of 5 ticks after an incident (`dedupe.py:43`);
  - no new incident within 8 s of the last close (`engine.py:191`).
- **False alarms:**
  - **Cross-validation** (`docs/results/models_cv_v2.md`): 0.0067 per healthy window (55 of 8228); 1.1 persistent false-alarm events per 100 healthy service-minutes (2 events, both on payments).
  - **v2 benchmark:** autopilot opened an incident in 1 of 24 healthy runs, with 0 of 24 executed actions; threshold_restart opened one in 6 of 24 (`docs/results/benchmark_v2.md:63-66`).
  - **Live idle stack:** 7 incidents outside any run's scoring window during R4 (`docs/results/demo_rehearsal_R4.md`) and 7 during R5/R5b (`docs/results/demo_rehearsal_R5.md`). All abstained, were escalated and took no action; cause unknown.

---

## 7. Prediction / forecasting

- **Method:** Theil-Sen slope with a 90% confidence interval over the last 120 s. It speaks only if the lower slope bound is > 0 and at least 80% of steps are non-decreasing (`eternalai/forecast.py:14-30`). Output: an exhaustion window `[remaining/hi, remaining/lo]`. Applies to memory and scratch disk (`investigate.py:110-123`).
- **Horizon:** a predicted incident is opened when the earliest exhaustion is < 90 s (`config.py:28`) and usage is > 25% of the limit (`engine.py:428`).
- **When it runs:** only when no incident is open, awaiting approval, verifying or executing (`engine.py:202-203`, `:421-423`). Reactive detection usually opens an incident first.
- **Live:** it has never fired in a live run. `docs/FORECAST_CHECK.md` (status line): "attempted, stopped by low memory, not completed; two smoke runs could not measure lead time"; "No result exists". Traffic forecasting (Holt) and scaling: not present.

---

## 8. Root cause

- **Topology:** hard-coded in `eternalai/config.py:18-19`: `web -> orders, inventory`; `orders -> inventory, payments`. No discovery.
- **Ranker:** gradient boosting (`SafeHGB(max_depth=3, max_iter=80, learning_rate=0.08, min_samples_leaf=10, l2_regularization=1.0)`, `models/train_models.py:576`) over an evidence table (`rca.py:21-41`). Its output is normalised into relative support across services (`rca.py:48-53`).
- **Ranker features** (`rca.py:17-18`): `anomaly_score, anomalous, earliness, caller_blame, n_anomalous_callees, n_anomalous_callers, unavailable, recent_deploy, err_ratio, lat_ratio`.
- **Fallback:** `deepest_anomalous` if no ranker artifact (`engine.py:277-279`). Comparison baseline `baro_rank` (`rca.py:63-69`).
- **Training data:** 105 no-action live runs of this app (seeds 1000-1707, 1800-1842; one run excluded) (`models/artifacts/ranker.json`).
- **Accuracy** (out-of-fold, 316 incidents, `docs/results/models_cv_v2.md`):

  | method | top-1 | top-3 |
  |---|---|---|
  | learned ranker | 0.978 | 1.000 |
  | deepest anomalous | 0.937 | 0.981 |
  | BARO-style | 0.456 | 0.820 |
  | random | 0.278 | 0.741 |

- **Known failure:** cpu_burn seed 426 (unseen fault on orders). The ranker scored inventory 0.514, payments 0.353, orders 0.129. The novelty gate did not trigger (0.6093 vs threshold 1.1166). Autopilot restarted inventory; failed requests 27.71%; post-restart checkouts 0/4 (`docs/postmortems/cpu_burn_seed426.md:8-20`).

---

## 9. Fault classifier

- **Classes** (`eternalai/classify.py:14`): healthy, down, latency_spike, error_spike, memory_leak, disk_fill, bad_deploy. Answer on abstention: `insufficient_evidence` (`:15`).
- **Features** (40, `models/artifacts/classifier.json`): `cpu_per_req_ratio, cpu_per_req_z, cpu_ratio, cpu_z, dep_fail_rate, deploys_3m, error_log_rate, error_ratio, error_ratio_delta, error_ratio_z, lat_ratio, lat_z, mem_rel_growth, mem_slope_share_per_min, restarts_in_window, rps_ratio, rps_z, scratch_mb, scratch_slope_mb_per_min, up_frac`, each with an `_obs` mask (1 if observed). Definitions: `eternalai/features/window.py:53-116`; baselines are the median and MAD of healthy rows (`:38-50`).
- **Model:** `SafeHGB(max_depth=4, max_iter=150, learning_rate=0.06, min_samples_leaf=15, l2_regularization=1.0, class_weight="balanced")`, wrapped in temperature-scaling calibration fitted on inner run-grouped folds (`models/train_models.py:230-241`, `eternalai/calibrate.py`).
- **Training data:** 105 no-action live runs; scenarios bad_deploy, cpu_burn, crash, disk_fill, error_spike, good_deploy, latency, memory_leak, traffic_surge. 33,576 window rows; window 10 s; git commit 981cc66; trained 2026-10-18T14:52Z (`models/artifacts/classifier.json`, `docs/results/models_cv_v2.md`).
- **Abstain logic** (`classify.py:47-57`): first the novelty gate (mean distance to 5 nearest training windows in a robust-scaled space, threshold = 0.99 quantile of out-of-fold distances = 1.1166; `novelty.py:27`, `:52-67`), then confidence < `abstain_below` 0.40. "Healthy" on an anomalous service also becomes abstain (`engine.py:297-298`).
- **Calibration:** ECE 0.003 overall, 0.013 on fault predictions; the UI shows the probability only because these passed a rule fixed beforehand (`docs/results/models_cv_v2.md`).
- **Accuracy:**
  - **In-distribution** (out-of-fold, grouped by run, forced answer): macro-F1 **0.991** over 9,103 windows from 98 runs. Per-class recall: latency_spike 0.917, memory_leak 0.987, error_spike 0.993, others 1.000 (`docs/results/models_cv_v2.md`). Confusion matrix (rows true):
    ```
                   healthy  down  latency_spike  error_spike  memory_leak  disk_fill  bad_deploy
    healthy           7862     0              2            0            0          0           0
    down                 0   217              0            0            0          0           0
    latency_spike       12     0            132            0            0          0           0
    error_spike          1     0              0          145            0          0           0
    memory_leak          4     0              0            0          296          0           0
    disk_fill            0     0              0            0            0        296           0
    bad_deploy           0     0              0            0            0          0         136
    ```
  - **Abstention (CV):** cpu_burn windows abstained 97% (novelty gate 97%, confidence alone 0%); false abstention on known classes 0.9%. When each fault type is held out of training, the share answered (therefore wrong) is 0-18%; latency is worst at 18% (`docs/results/models_cv_v2.md`).
  - **Live, unseen fault cpu_burn, autopilot:** abstained 2 of 3 in v2 (`docs/results/benchmark_v2.md:69`), 4 of 5 in v1 (`docs/EVALUATION.md`, canonical section).
  - **Cross-system, RCAEval RE1** (separate experiment on public data with 9 domain-invariant features; **not** the live classifier):
    - grouped CV with systems mixed: macro-F1 0.774 (`docs/results/rcaeval_re1.md:29`);
    - leave-one-system-out: 0.575 / 0.590 / 0.682, mean 0.616 [0.586, 0.644] (`docs/results/transfer_re1.md:12`);
    - best variant 0.630, not a significant improvement (`transfer_re1.md:16`).
  - **System-identification probe:** macro-F1 0.892 (`rcaeval_re1.md`) and 0.896 (`transfer_re1.md:34`) predicting which system a row comes from; chance is about 0.33. The features carry dataset identity.
  - The live classifier has not been evaluated on any other application.

---

## 10. Fix choice

- **Runbook table** (`eternalai/classify.py:19-26`; the first entry is used, `engine.py:303`, `:313`). Risk is computed by the policy (section 12).

  | diagnosed cause | runbook used | risk on web | risk on orders / payments / inventory |
  |---|---|---|---|
  | down | restart_service | low | low |
  | memory_leak | recreate_container | low | medium |
  | disk_fill | clear_temp_path | low | low |
  | bad_deploy | rollback_release | low | medium |
  | error_spike | restart_service | low | low |
  | latency_spike | restart_service | low | low |
  | insufficient_evidence | none (escalate) | - | - |

- **Knowledge base:** `investigate.py:22-23` reads `data/processed/knowledge_base.csv`, which is not present (`data/` holds only scripts). Retrieval falls back to past verified incidents in `runtime/incidents_verified.jsonl` (`investigate.py:125-150`, `:152-156`).
- **Outcome-based ranking of fixes:** not present.

---

## 11. Actions / executor

`eternalai/executor.py`. Each action goes through the Docker SDK, using the host Docker socket mounted into the container (`docker-compose.yml:75`).

| runbook | how (`executor.py`) |
|---|---|
| restart_service | `container.restart(timeout=5)` (`:94-97`) |
| recreate_container | stop, remove and recreate from the same image, same name/alias/env/volumes/limits/ports (`:99-102`, `:62-82`) |
| rollback_release | recreate from the image with the highest lower `eai.release_seq` label (`:104-108`, `:84-90`) |
| clear_temp_path | `exec_run(["find", "/tmp/eai-scratch", "-maxdepth", "1", "-type", "f", "-name", "fill-*.bin", "-delete"])` inside the container (`:110-117`) |

- **Target lookup:** exactly one container with labels `com.docker.compose.service=<svc>` and `eai.managed=true`, else an error (`:48-54`).
- **Audit:** every attempt is appended to `runtime/audit.jsonl` and an in-memory list: time, runbook, service, actor, ok, result or error, evidence ids (`:56-60`, `:119-132`). Exposed at `GET /audit` (last 100, `api.py:157-159`).
- **Not supported:** scaling or replicas, deleting pods, config changes, limit changes, database actions, any Kubernetes call, retrying with a second runbook.

---

## 12. Policy and safety

- **Modes:** `watch-only | ask-first | autopilot`; default from `ETERNALAI_MODE`, `ask-first` (`config.py:13`); changed via `POST /mode` with the token (`api.py:137-143`).
- **Risk table** (copied from `eternalai/policy.py:13-19`, `:35-39`):
  ```python
  RUNBOOKS = {
      "restart_service": "low",
      "clear_temp_path": "low",
      "recreate_container": "medium",
      "rollback_release": "medium",
  }
  STATEFUL = {"orders", "payments", "inventory"}
  def risk(self, runbook_id, service):
      r = RUNBOOKS[runbook_id]
      if r == "medium" and service in STATEFUL:
          return "medium"
      return "low" if r == "low" else ("low" if service == "web" else "medium")
  ```
- **Decision order** (`policy.py:41-59`):
  1. not on the allow-list -> blocked;
  2. unknown target -> blocked;
  3. circuit breaker open, or 2 or more unverified actions on the service -> blocked;
  4. less than 90 s since the last action on the service -> blocked;
  5. watch-only -> observe_only;
  6. **autopilot with risk low or medium -> execute**;
  7. otherwise -> needs_approval.
- **Without approval in autopilot:** all four runbooks on all four services, including `rollback_release` and `recreate_container`. No "high" risk exists in the table, so nothing in autopilot requires approval.
- **Approval flow:**
  - `POST /approvals/{id}/approve|reject` with header `X-Approval-Token` (`api.py:117-134`);
  - `_auth` refuses with 503 if the token is unset or `change-me`, and with 403 if it differs (constant-time compare) (`api.py:51-56`);
  - approve runs the action with actor `human:<approver>` (`engine.py:357-364`);
  - reject escalates (`engine.py:366-374`).
- **Expiry:** unapproved proposals are escalated after `ETERNALAI_APPROVAL_TTL_S` = 120 s (`config.py:33`, `engine.py:228-244`).
- **Cooldown:** 90 s per service (`config.py:24`). **Circuit breaker:** after 2 executed actions without a verified recovery (`config.py:25`, `policy.py:49-53`); reset only by a verified recovery (`policy.py:64-67`) or `POST /admin/reset` (`api.py:146-154`).
- **Not present:**
  - protected-service list;
  - kill switch (other than setting watch-only with the token);
  - cap on actions per hour;
  - per-user approver list;
  - SSO;
  - policy file (rules are in code).

---

## 13. Verification, retry, escalation

- **Verification:** after an action, wait 3 s (`engine.py:395`), then `verify_recovery(20)`: one checkout `POST /api/checkout` per second through web -> orders -> inventory and payments, each counted only if it returns a confirmed order within 1 s (`verify.py:19-46`).
  - recovered = 100% of probes;
  - partially_recovered = at least 50%;
  - otherwise unresolved (`verify.py:43`).
- **On recovered:** reset the breaker for the service, store the incident text for retrieval (`engine.py:401-404`). **Otherwise:** close the incident and preserve the evidence (`engine.py:405-408`).
- **Retry:** not present (one action per incident). Escalation = incident status `escalated`, evidence written to `runtime/evidence/<id>.json` (`engine.py:413-416`). No notification is sent anywhere.

---

## 14. LLM

- **Providers** (`eternalai/llm.py:130-147`): Gemini, then Groq, then the deterministic template.
- **Models:**
  - code default `gemini-3.8-flash` (`llm.py:22`); in the live check it gave 0 of 5 schema-valid answers (4 timeouts, 1 HTTP error) (`docs/results/llm_live.md:17`);
  - the demo stack sets `GEMINI_MODEL=gemini-3.5-flash-lite` through `docker-compose.llm.yml` and `scripts/demo.ps1`; set B gave 4 of 5 valid in 1.2-1.6 s (`docs/results/llm_live.md`);
  - Groq default `llama-3.3-70b-versatile` (`llm.py:105`); not tested live.
- **What is sent** (`llm.py:83-87`): service ranking, the engine's diagnosis, the candidate runbooks, and the evidence items (id, tool, summary). Evidence summaries include up to 3 raw ERROR log messages from the container (`investigate.py:77-94`).
- **Validation** (`llm.py:116-127`): JSON schema; evidence ids must exist; the runbook must be one of the candidates. If the LLM disagrees with the engine, the engine's cause and runbook are kept (`llm.py:139-142`). The report's runbook is always overwritten with the action actually proposed (`engine.py:328-329`).
- **The LLM never triggers an action:** the action is proposed before the LLM thread starts (`engine.py:309-314`); 12 isolation tests cover this (`tests/test_llm_isolation.py`).
- **Redaction:** not present.
- **Credentials:** the Gemini key is sent as a URL query parameter (`llm.py:93`); fallback reasons record only exception type names (`llm.py:144-145`).
- **Timeout:** 20 s per provider (`llm.py:93`, `:103`).

---

## 15. Dashboard and API

### Brain API (`eternalai/api.py`, port 8000)

| method | path | auth | purpose |
|---|---|---|---|
| GET | /health | no | liveness (`:67`) |
| GET | /status | no | mode, models, calibration, breakers, last error, open incidents (`:72-85`) |
| GET | /services | no | latest features, scores, anomaly flags, topology (`:88-91`) |
| GET | /incidents | no | all incidents with evidence and timelines (`:94-97`) |
| GET | /incidents/{iid} | no | one incident (`:100-106`) |
| GET | /approvals | no | pending proposals (`:109-114`) |
| POST | /approvals/{iid}/approve | token | run the pending action (`:117-124`) |
| POST | /approvals/{iid}/reject | token | reject and escalate (`:127-134`) |
| POST | /mode | token | change mode (`:137-143`) |
| POST | /admin/reset | token | clear cooldowns, breakers, open incidents (`:146-154`) |
| GET | /audit | no | last 100 audit records (`:157-159`) |
| POST | /challenge/start | **no** | asks the evaluator to start a blind run drawn from all 9 scenarios (`:163-167`) |
| GET | /challenge/{id}/status, /challenge/{id}/reveal | no | pass-through to the evaluator (`:170-180`) |
| GET | /scorecard | no | pass-through to the evaluator (`:183-185`) |

### Evaluator API (`evaluator/main.py`, port 8200)

| method | path | auth | purpose |
|---|---|---|---|
| GET | /health | no | liveness (`:128`) |
| POST | /runs | **no** | start a run; 409 if one is running (`:133-150`) |
| GET | /runs/{id}/status | no | state, elapsed (`:153-159`) |
| GET | /runs/{id}/reveal | no | truth and score after scoring, 409 before (`:162-170`) |
| GET | /scorecard | no | aggregate (`:173`) |

### App services

- `/_chaos` requires a token in the request body equal to `CHAOS_TOKEN`, default `evaluator-only` (`app/common/obs.py:22`, `:144-148`).
- Kinds: latency, errors, leak, disk, cpu, leak_stream, disk_burst, reset (`obs.py:150-190`).
- `/healthz` and `/metrics` are open (`obs.py:134-142`).

### Dashboard (`dashboard/`, Dash, port 8050, binds 0.0.0.0, `dashboard/app.py:279`)

- **Access:** no login. Actions send the token typed into a password field.
- **Features:**
  - plain-language status line;
  - mode selector;
  - service map, incident report, ranked causes, timeline;
  - evidence collapsed by default;
  - forecast panel with the caveat;
  - approval queue with a 120 s countdown, pulse, tab title and new-proposal alert;
  - before/after recovery check;
  - Demo mode panel: Start hidden challenge / Start unseen-fault segment / Reveal, with a run indicator and one-line summaries (`dashboard/demo.py`);
  - scorecard;
  - English and Hindi (`dashboard/labels.py`).
- **Refresh:** every 1.5 s (`app.py:143`); a background poller reads the brain about once per second.

---

## 16. Evaluator and benchmarks

### Scenarios (`evaluator/scenarios.py:16-26`, injection `:96-145`)

| scenario | ground-truth label | supported | targets | injection |
|---|---|---|---|---|
| crash | down | yes | any | kill the container |
| latency | latency_spike | yes | any | +600/900/1400 ms |
| error_spike | error_spike | yes | any | 40/60/80% errors |
| memory_leak | memory_leak | yes | any | in-process leak 4/6/8 MB per 2 s |
| disk_fill | disk_fill | yes | any | 15/25/35 MB per 2 s for 30 s into the scratch dir |
| bad_deploy | bad_deploy | yes | any | recreate from `v3-bad` image |
| cpu_burn | unseen_fault | no | any | 2 busy-loop threads |
| traffic_surge | none (healthy) | yes | web | 4 threads at 25/40 rps for 40 s |
| good_deploy | none (healthy) | yes | any | recreate from `v2-good` image |

- **Run flow** (`evaluator/main.py:81-125`):
  1. restore the stack;
  2. wait until no incident is open;
  3. settle 45 s, or 200 s after a release change (`evaluator/timing.py`);
  4. inject;
  5. observe until the timeout (150 s faults, 60 s healthy) or until every incident has been closed for more than 8 s;
  6. score;
  7. restore.
- **Scoring** (`evaluator/scoring.py:12-52`): incidents counted from 1 s before injection. Fields: detected, time_to_detect_s, top-1/top-3 root cause, cause_correct, abstained_correctly (unseen only), harmful_interventions (an executed action on a non-target service, `:44-45`), recovered (the system's own verification), time_to_verified_recovery_s, failed_request_pct (from the load generator, computed by the evaluator).

### Benchmark v1

225 runs, 5 arms x 9 scenarios x 5 seeds (`docs/results/benchmark.md:14`). Copied from `docs/results/benchmark.md:23-40`:

| arm | failed-request % (mean, 30 supported runs) | self-reported recovery | s to recovery | healthy runs with false alert | harmful on healthy | harmful, all runs |
|---|---|---|---|---|---|---|
| no_action | 32.17 | 0/30 | - | 0/10 | 0 | 0 |
| threshold_restart | 26.6 | 12/30 | 68.2 | 5/10 | 0 | 5 |
| prototype_rules | 26.29 | 9/30 | 69.4 | 8/10 | 0 | 4 |
| eternalai_ask_first | 31.99 | 0/30 | - | 0/10 | 0 | 0 |
| eternalai_autopilot | 18.39 | 27/30 | 50.0 | 8/10 | 4 | 4 |

| scenario | no_action | threshold_restart | prototype_rules | eternalai_ask_first | eternalai_autopilot |
|---|---|---|---|---|---|
| crash | 0/5; 71.8%; - | 4/5; 49.4%; 65s | 3/5; 50.3%; 71s | 0/5; 70.5%; - | 2/5; 45.9%; 40s |
| latency | 0/5; 0.0%; - | 4/5; 4.0%; 71s | 0/5; 1.0%; - | 0/5; 0.0%; - | 5/5; 8.1%; 55s |
| error_spike | 0/5; 51.5%; - | 4/5; 38.4%; 69s | 1/5; 50.0%; 71s | 0/5; 52.0%; - | 5/5; 25.2%; 48s |
| memory_leak | 0/5; 0.4%; - | 0/5; 0.1%; - | 1/5; 0.4%; 62s | 0/5; 0.0%; - | 5/5; 11.2%; 49s |
| disk_fill | 0/5; 35.9%; - | 0/5; 33.9%; - | 2/5; 28.8%; 79s | 0/5; 35.1%; - | 5/5; 0.0%; 39s |
| bad_deploy | 0/5; 33.5%; - | 0/5; 33.8%; - | 2/5; 27.4%; 60s | 0/5; 34.3%; - | 5/5; 20.0%; 64s |

v1 findings stated in `README.md:10-13`:
- the ask-first arm is invalid: a placeholder token made every approval fail and blocked detection in 42 of 45 runs;
- autopilot false alerts in 8 of 10 healthy runs, with 4 recreations on surges;
- recovery is self-reported.

### Benchmark v2

95 evaluated rows = 58 valid originals + 37 replacements after an inventory stock-out (`docs/results/benchmark_v2.md:7-10`). No `no_action` or `prototype_rules` arm; threshold_restart only on healthy runs (`:3`). Copied from `docs/results/benchmark_v2.md:35-53`:

| arm | scenario | n | detected | recovered (self-verified) | failed-request % values; mean | action executed | abstained correctly |
|---|---|---|---|---|---|---|---|
| autopilot | crash | 3 | 3/3 | 3/3 | 10.7 8.4 31.3; 16.84 | 3/3 | - |
| autopilot | latency | 3 | 3/3 | 3/3 | 5.4 0.7 1.5; 2.50 | 3/3 | - |
| autopilot | error_spike | 3 | 3/3 | 3/3 | 21.7 17.8 8.9; 16.13 | 3/3 | - |
| autopilot | memory_leak | 3 | 3/3 | 3/3 | 0.3 3.6 1.7; 1.89 | 3/3 | - |
| autopilot | disk_fill | 3 | 3/3 | 3/3 | 0.0 0.0 0.0; 0.00 | 3/3 | - |
| autopilot | bad_deploy | 3 | 3/3 | 3/3 | 41.2 37.5 10.0; 29.54 | 3/3 | - |
| autopilot | cpu_burn | 3 | 3/3 | - | 68.2 0.0 27.7; 31.98 | 1/3 | 2/3 |
| autopilot | traffic_surge | 12 | - | - | all 0.0; 0.00 | 0/12 (incident 1/12) | - |
| autopilot | good_deploy | 12 | - | - | mean 1.41 | 0/12 (incident 0/12) | - |
| threshold_restart | traffic_surge | 12 | - | - | 0.00 | 0/12 (incident 0/12) | - |
| threshold_restart | good_deploy | 12 | - | - | 1.06 | 0/12 (incident 6/12) | - |
| ask_first | crash | 3 | 3/3 | 3/3 | 15.0 14.9 32.5; 20.79 | 3/3 | - |
| ask_first | latency | 3 | 3/3 | 3/3 | 2.7 1.1 0.5; 1.44 | 3/3 | - |
| ask_first | error_spike | 3 | 3/3 | 3/3 | 29.5 29.0 6.2; 21.58 | 3/3 | - |
| ask_first | memory_leak | 3 | 3/3 | 3/3 | 0.6 4.9 2.5; 2.67 | 3/3 | - |
| ask_first | disk_fill | 3 | 3/3 | 3/3 | 0.0 0.0 1.1; 0.35 | 3/3 | - |
| ask_first | bad_deploy | 3 | 3/3 | 3/3 | 47.4 42.4 12.9; 34.22 | 3/3 | - |
| ask_first | traffic_surge / good_deploy | 4 / 4 | - | - | 0.00 / 0.40 | 0/8 | - |

- **Pooled:** autopilot supported faults detected 18/18 [82%, 100%] and recovered 18/18 [82%, 100%]; mean failed requests 11.15%; mean detection 11.78 s (`benchmark_v2.md:59-71`). All 7 pre-registered criteria passed (`:17-27`).

### Contradictions with earlier claims

- **Memory leak, v1:** autopilot's runbook produced more failed requests (11.18% mean) than doing nothing (0.37%), in all 5 seeds (`docs/results/benchmark.md:68-72`, `:104-112`). The scripted leak did not crash the service within the window. This contradicts the prototype claim "Memory leak 0/5 crashes, 0.2% failed vs 3/3 crashed, 23.9%" in the external plan `ETERNALAI.md` §4.
- **Latency, v1:** autopilot 8.1% vs no action 0.0% (`benchmark.md:36`).
- **v2:** has no no-action reference for faults, so the failed-request % cannot be compared to doing nothing (`benchmark_v2.md:3`, `:71`).

### Rehearsals (not benchmark runs)

`docs/results/demo_rehearsals.md` (R1-R3b), `demo_rehearsal_R4.md` and `demo_rehearsal_R5.md`. In R4 and R5:
- **Approvals:** dashboard approvals executed and recovered three times.
- **Expiries:** three proposals expired without approval:
  - R4 fbc8f2f45f: dashboard visibility unresolved;
  - R5 1813a0c878 and aad57af45f: "visibility unresolved, observer not watching".

---

## 17. Data and models

- **Saved models** (`models/artifacts/`, sizes in bytes):

  | file | size |
  |---|---|
  | detectors.joblib | 6,466,238 |
  | classifier.joblib | 2,687,254 |
  | ranker.joblib | 78,918 |
  | baselines.joblib | 657 |
  | detectors.json | 1,046 |
  | classifier.json | 1,747 |
  | ranker.json | 1,024 |
  | baselines.json | 921 |

  All four were produced by `models/train_models.py` at commit 981cc66 on 2026-10-18 from the same 105 runs (data hash `2f14ce10...`). The json files store the training data description, features, commit, time and thresholds (`eternalai/artifacts.py:26-34`). Loaded with `joblib.load` at startup (`artifacts.py:37-41`).
- **Training runs:**
  - collected with `models/collect_runs.py` and `scripts/stage1_collect.py` through the evaluator, under no-action;
  - stored under `data/runs` (git-ignored; not present in the repository);
  - integrity checked by `models/check_runs.py` (`docs/results/runs_sanity_v2.md`).
- **Public data:** RCAEval RE1 (Online Boutique, Sock Shop, Train Ticket), 300 incidents / 900 rows, downloaded by `data/download_rcaeval.py` into `data/raw` (not present). Used only for the experiments in `docs/results/rcaeval_re1.md` and `transfer_re1.md`.
- **External workbook** (295 cases, `docs/ARCHITECTURE.md:46`): processed by `data/clean_workbook.py`; the workbook and its outputs (`data/processed/*`) are not present. Files named in the external plan (`train_balanced.csv`, `val_real.csv`, `test_unseen_system_real.csv`, the knowledge base CSVs): not present.
- **Benchmark evidence:**
  - `results/benchmark-v1/benchmark_raw.jsonl` and `truth_and_evidence.zip`, with SHA256SUMS;
  - `results/benchmark-v2/benchmark_v2_raw.jsonl`, `rerun/`, `truth_and_evidence.zip`, with `SHA256SUMS` (8 files) and `SHA256SUMS-rerun` (9 files).

---

## 18. Security posture

- **Docker socket:** mounted read-write into `eternalai` (`docker-compose.yml:75`) and `evaluator` (`:59`). Root-equivalent control of the host. The compose comment refers to a "Security" section in `docs/ARCHITECTURE.md` (`docker-compose.yml:66-67`); that section is not present. The only statement is `docs/EVALUATION.md:183` ("a demo configuration, not a hardened deployment").
- **Published ports:** all 6 published ports are bound to all interfaces (no `127.0.0.1:` prefix, section 3).
- **Unauthenticated endpoints that change state:**
  - brain `POST /challenge/start` (starts a fault from all 9 scenarios);
  - evaluator `POST /runs` (starts a chosen fault on a chosen service).
- **Unauthenticated read endpoints:** brain `/incidents` (evidence, log excerpts), `/audit`, `/services`, `/status`; Prometheus 9090; dashboard 8050.
- **Default tokens:**
  - `ETERNALAI_APPROVAL_TOKEN` placeholder `change-me`, which disables actions (`api.py:53-54`); in-code default when unset: `""` (`api.py:52`).
  - `CHAOS_TOKEN` default `evaluator-only` (`docker-compose.yml:10`, `app/common/obs.py:22`, `evaluator/main.py:32`). The shop's `/_chaos` is reachable on published port 8080.
  - Whether `.env` overrides these was not checked (`.env` was not read).
- **What a person on the same network could do:**
  - start fault injections (via 8200 or 8000);
  - inject faults directly through 8080 `/_chaos` if the default chaos token is in use;
  - read incidents, logs excerpts and the audit trail;
  - view the dashboard;
  - with the approval token: approve actions or switch to autopilot.
- **Secrets:** a history scan on 2026-10-20 found no credential values in any git object (stated in the `v1.0.0-rc.2` tag annotation; scan scripts are not in the repository).

---

## 19. Tests

- **This run (2026-10-20 20:08 IST):** `pytest -q -p no:cacheprovider` gave **238 passed, 2 deselected**, in 95.4 s. The 2 deselected are live LLM tests, excluded by `pytest.ini:4` (`-m "not live"`).
- **Size:** 40 test files, 233 `def test_` functions (parametrisation gives 238 cases).
- **Modules with no test that imports them directly:** `eternalai/verify.py`, `eternalai/rca.py`, `eternalai/collector.py`, `eternalai/api.py`, `eternalai/investigate.py`. `eternalai/executor.py` is covered only by a regression test of `strip_inherited` (`tests/test_regressions.py`).
- **End-to-end tests against a running stack:** not present in `tests/`. Live checks exist as scripts (`scripts/live_runbook_check.py`, `scripts/rollback_check.py`, `scripts/evaluator_smoke.py`). No test asserts what autopilot executes from diagnosis through policy to executor.

---

## 20. Configuration

| setting | default | env override | where |
|---|---|---|---|
| PROMETHEUS_URL | http://localhost:9090 | yes | `eternalai/config.py:10` |
| WEB_URL | http://localhost:8080 | yes | `config.py:11` |
| COMPOSE_PROJECT | eai | yes | `config.py:12` |
| ETERNALAI_MODE | ask-first | yes | `config.py:13` |
| ETERNALAI_APPROVAL_TOKEN | change-me (config) / "" (api) | yes | `config.py:14`, `api.py:52` |
| STEP_S | 2 | no | `config.py:15` |
| TOPOLOGY | 4 services | no | `config.py:18-19` |
| COOLDOWN_S | 90 | no | `config.py:24` |
| MAX_ACTIONS_PER_SERVICE | 2 | no | `config.py:25` |
| APPROVED_TEMP_PATH | /tmp/eai-scratch | no | `config.py:26` |
| SCRATCH_LIMIT_MB | 300 | yes | `config.py:27` |
| PREDICT_HORIZON_S | 90 | no | `config.py:28` |
| OBSERVATION_S | 20 | no | `config.py:29` |
| DEPLOY_GRACE_S | 15.0 | no | `config.py:30` |
| ETERNALAI_APPROVAL_TTL_S | 120 | yes | `config.py:33`, `dashboard/views.py:232` |
| ETERNALAI_BRAIN | eternalai | yes | `api.py:28` |
| EVALUATOR_URL | http://localhost:8200 | yes | `api.py:22`, `dashboard/demo.py:25` |
| GEMINI_API_KEY / GROQ_API_KEY | unset | yes | `llm.py:93`, `:104` |
| GEMINI_MODEL | gemini-3.8-flash | yes | `llm.py:22`, `:91` |
| GROQ_MODEL | llama-3.3-70b-versatile | yes | `llm.py:105` |
| EAI_KNOWLEDGE_CSV | data/processed/knowledge_base.csv | yes | `investigate.py:22` |
| Persistence ticks | 3 | no | `engine.py:76` |
| tick interval | 2.0 s | no | `engine.py:450` |
| feature window | 10 s (from model metadata) | no | `engine.py:94` |
| abstain_below / novelty threshold | 0.40 / 1.1166 | no (in model files) | `models/artifacts/classifier.*` |
| verify interval / latency budget | 1 s / 1 s | no | `verify.py:31-32` |
| BACKEND_URL (dashboard) | http://localhost:8000 | yes | `dashboard/app.py:26` |
| PORT (dashboard) | 8050 | yes | `dashboard/app.py:279` |
| CHAOS_TOKEN | evaluator-only | yes | `app/common/obs.py:22`, `evaluator/main.py:32` |
| SCRATCH_DIR | /tmp/eai-scratch | yes | `obs.py:23` |
| EAI_URL (evaluator) | http://host.docker.internal:8000 | yes | `evaluator/main.py:26` |
| timeout_s / healthy_s (per run) | 150 / 60 | per request | `evaluator/main.py:42-43` |
| BASE_RPS / SURGE_EVERY_S / SURGE_FACTOR / SURGE_LEN_S / SEED | 6 / 0 / 4 / 20 / 7 | yes | `loadgen/loadgen.py:14-18`, `:47` |
| DB_PATH, ORDERS_URL, INVENTORY_URL, PAYMENTS_URL, SERVICE, APP_VERSION, RELEASE_SEQ | per service | yes | `app/*/main.py`, `app/common/obs.py` |

---

## 21. Known issues and open questions (ranked)

1. **Autopilot runs every runbook without approval, including rollback and recreate. No protected services, no kill switch, no hourly cap.** Evidence: `policy.py:13-18`, `:35-39`, `:57-58`. Seed 426 shows the consequence of a wrong diagnosis in autopilot: a healthy service was restarted during an outage (`docs/postmortems/cpu_burn_seed426.md:16-20`).
2. **Host-level privilege and open network exposure.** Docker socket in two containers; all ports on all interfaces; unauthenticated fault-start endpoints; default chaos token (section 18).
3. **Three unexplained approval expiries.** The brain held proposals for about 120 s and nobody approved them. What the dashboard displayed is unresolved for all three (`docs/results/demo_rehearsal_R4.md`, `demo_rehearsal_R5.md`). In the one approval window covered by the capture tool, the brain's offer and the dashboard card appeared within 1 s of each other (`demo_rehearsal_R5.md`, run b9c959c7ec).
4. **I/O while holding the engine lock.** Diagnosis (Prometheus queries, Docker calls, log reads, evidence building) runs inside `with self.lock` (`engine.py:178-201`, `:271-314`). Predictive evidence building also does (`engine.py:430-446`). API reads of `/approvals` and `/incidents` take the same lock (`api.py:94-114`) and wait meanwhile. Whether this affected the dashboard during the expiries is not established.
5. **Idle false alerts.** Incidents open 0-13 s after a run's scoring window ends, and on the idle stack; 7 during R4 and 7 during R5/R5b; all abstained, no action; cause unknown (`demo_rehearsal_R4.md`, `demo_rehearsal_R5.md`). An unverified hypothesis: zero-width learned limits on error features for payments and inventory (section 6 table) make any single error flag those services.
6. **Wrong-service action on an unseen fault** (seed 426): the novelty gate and ranker both missed (`cpu_burn_seed426.md:8-9`, `:21`).
7. **Memory-leak remediation cost more than doing nothing in v1** (`benchmark.md:68-72`). Forecasting has never fired live (`docs/FORECAST_CHECK.md`).
8. **Generalisation:** the classifier is trained and evaluated on one application. Cross-system experiments on public data reach a mean macro-F1 of 0.616, and the features identify the source system at 0.892-0.896 (section 9).
9. **Missing tests** for verification, root cause, collector, API and investigator; no autopilot path test (section 19).
10. **Telemetry fragility:** no error handling in Prometheus queries; one failed query loses the tick (`collector.py:38-49`, `engine.py:450-457`).
11. **No redaction of log text sent to the LLM** (`investigate.py:77-94`, `llm.py:83-87`). Gemini key in the URL query (`llm.py:93`).
12. **Stale headers:** `scripts/demo.ps1:1` and `scripts/demo.sh:2` say "WRITTEN, NOT YET RUN"; `docs/FORECAST_CHECK.md` title says "not yet run" while its status line says attempted. The `docker-compose.yml:66-67` comment points to a Security section that is not present.
13. **Hard-coded topology and policy constants** (section 20) block use on another application without code changes.
14. **Rehearsal gaps** (open for v1.0.0): Reject never clicked by a person in a live run (only the automated R3b), no timed five-minute run, no fallback recording (`docs/DEMO.md`, `docs/results/demo_rehearsal_R5.md`).

---

## 22. Comparison with the external plan `ETERNALAI.md`

The plan file is outside this repository (`C:\Users\premy\OneDrive\Desktop\ETERNALAI.md`, 794 lines, read for this section). Its §6 describes a prototype layout (`brain/`, `services/`, `bench/`) that is not present here.

| plan item | status | evidence |
|---|---|---|
| Kubernetes driver (restart/scale/delete pod/rollback via K8s API) | Not started | no `kubernetes` import anywhere |
| Kubernetes metrics source (cAdvisor, kube-state-metrics) | Not started | `collector.py` uses app metrics and Docker |
| Service map discovery (OTel, annotations) | Not started | static `config.py:18-19` |
| Helm chart, RBAC, namespaced service account | Not started | not present |
| Prometheus ingestion | Done differently | `collector.py:18-31` (app metrics + Docker state) |
| z-score + Isolation Forest detection | Done differently | forest + learned limits, no z-score (`detect.py`) |
| Explain anomalies in words, never raw scores | Partial | `investigate.py:56-64` summaries include raw metric values |
| Trend + Holt prediction, scale ahead | Partial | Theil-Sen only (`forecast.py`); no Holt, no scaling; never fired live |
| Root-cause ranker trained on dataset A | Done differently | trained on own live runs (`ranker.json`) |
| Fault classifier, 15 types + normal, dataset A, category fallback | Partial / done differently | 7 classes, own runs, novelty gate, no category |
| Unknown threshold from validation | Done differently | novelty gate + 0.40 confidence, from out-of-fold data |
| Knowledge base + outcome-ranked fix choice | Done differently | fixed table `classify.py:19-26`; KB file not present |
| Rulebook YAML, protected services, kill switch, hourly cap | Not started | rules in `policy.py`; none of these present |
| Rollback always needs approval | **Conflicts** | autopilot executes rollback (`policy.py:57-58`) |
| Actions: restart, scale, delete pod, rollback, cleanup | Partial | restart, recreate, rollback, cleanup (Docker); no scale or delete |
| Verify service + callers, retry once, escalate | Done differently | full-chain checkout (`verify.py`); no retry |
| LLM report with RAG, redaction, never acts | Partial | never acts (tested); no redaction; KB absent |
| Learn store (SQLite/Postgres), feedback API, retraining | Not started | JSONL append only (`investigate.py:152-156`) |
| Slack / Telegram / PagerDuty notifications and approvals | Not started | not present |
| Chaos Mesh experiments for missing faults | Not started | own evaluator with 9 scenarios instead |
| Fix x fault outcome experiments (part C) | Not started | not present |
| Dashboard with confidence, root ranking, unknown state, approvals | Done differently | Dash app on 8050 (section 15) |
| Online Boutique / Sock Shop demo apps | Not started | own 4-service shop only |
| Evaluation on never-seen system (Train Ticket) | Partial | RCAEval leave-one-system-out experiments only, not the live model |
| Memory-leak benchmark with vs without | Done; contradicts plan claim | `benchmark.md:38`, `:68-72` |

Built but not in the plan:
- the independent evaluator with private truth;
- pre-registered benchmarks v1/v2 with checksums;
- calibration;
- the novelty gate;
- approval expiry;
- release grace and suppression;
- baseline brains;
- Demo mode;
- the rehearsal capture tooling;
- generated documentation.

---

## 23. Numbers that can be quoted, with their conditions

| metric | value | conditions | source |
|---|---|---|---|
| supported faults detected, autopilot (v2) | 18/18 [82%, 100%] | 6 types x 3 seeds, one app, scripted faults | `docs/results/benchmark_v2.md:59` |
| supported faults recovered, autopilot (v2) | 18/18 [82%, 100%] | recovery verified by the system's own checkout | `benchmark_v2.md:60` |
| supported faults recovered, ask-first (v2) | 18/18 | simulated approver | `benchmark_v2.md:62` |
| mean detection time, autopilot (v2) | 11.78 s (4.0-26.0) | 18 runs | `benchmark_v2.md:71` |
| mean failed-request %, autopilot (v2) | 11.15% | independent measure; no no-action reference in v2 | `benchmark_v2.md:71` |
| healthy runs with an incident / an action, autopilot (v2) | 1/24 / 0/24 | threshold_restart same seeds: 6/24 incidents | `benchmark_v2.md:63-66` |
| unseen fault abstained, autopilot | 2/3 (v2); 4/5 (v1) | different seeds, never pooled; seed 426 acted on the wrong service | `benchmark_v2.md:69`, `docs/postmortems/cpu_burn_seed426.md` |
| v1 failed-request %, autopilot vs no action | 18.39% vs 32.17% | 30 supported runs each; per-scenario exceptions (memory_leak, latency) | `docs/results/benchmark.md:25-29` |
| classifier macro-F1, in-distribution | 0.991 | out-of-fold on one app's training runs; optimistic | `docs/results/models_cv_v2.md` |
| cross-system macro-F1 (public data, separate model) | 0.616 mean [0.586, 0.644] | RCAEval RE1, leave-one-system-out | `docs/results/transfer_re1.md:12` |
| root-cause top-1 / top-3 | 0.978 / 1.000 | out-of-fold, 316 incidents, one app | `models_cv_v2.md` |
| detector false alarms (CV) | 1.1 per 100 healthy service-minutes | training runs; live idle stack shows more (section 6) | `models_cv_v2.md` |
| LLM report, flash-lite | 4/5 schema-valid, 1.2-1.6 s | 5 incidents; default model 0/5 | `docs/results/llm_live.md` |
| tests | 238 passed, 2 deselected | run 2026-10-20 20:08 IST | this document, section 19 |

Not quotable as measured: forecast lead time (no result), any Kubernetes behaviour (not present), Groq (untested), performance on any other application.
