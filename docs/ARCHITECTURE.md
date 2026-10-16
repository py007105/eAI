# EternalAI architecture

EternalAI is a predictive cloud recovery assistant. It observes telemetry from a four-service app, detects anomalies, diagnoses the root-cause service, proposes or executes an approved runbook, and verifies that a synthetic checkout works again. It escalates when it cannot fix something.

This is a new codebase. It is not a fork and not a collection of copied repos. Code is copied only where the licence allows, with attribution in `NOTICE`; otherwise patterns are re-implemented. Python 3.11+ only, FastAPI everywhere, Pydantic schemas, Dash for the dashboard.

## Data flow

```
loadgen --> web --> orders --> payments / inventory       (app/, 4 FastAPI services)
                |        metrics (prometheus-client), JSON logs, OTel traces
                v
          Prometheus (+Loki, +Jaeger/OTel collector)
                v
   eternalai backend:  features -> detect -> classify -> rca -> investigate -> llm
                                         \-> forecast        \-> policy -> executor -> verify
                v REST
          dashboard (Dash)          evaluator (separate container, private ground truth)
```

The evaluator injects faults and writes ground truth to a volume the EternalAI container does not mount. EternalAI never receives a fault name, target, flag or answer. Truth is read only by the scorer.

## Components, sources of ideas, and what we build

| Component | Idea from | We build |
|---|---|---|
| `app/` four services with real DB/state, metrics, logs, traces, versioned image tags | own prototype (services/app.py), predictive-reliability-platform stack shape | New FastAPI services; each build is tagged so rollback to the previous tag is a real image swap. |
| `loadgen/` | prototype loadgen, predictive-reliability-platform chaos load idea | asyncio + httpx: browsing, sandbox checkout, variable levels, healthy surges. |
| `features/` | prototype detect/predict, dataset schema | One rolling-window code path shared by training and live inference. Missing stays NaN with explicit masks. |
| `detect/` | prototype (per-service IsolationForest), aiops-anomaly-detector (percentile threshold), AIOps-Driven (chaos-labelled training windows) | IsolationForest per service trained on healthy, traffic-normalised windows. The score is not shown as a probability. Fails closed (reports "model unavailable"), never "normal". |
| `classify/` | own dataset and baseline findings | Gradient-boosted classifier on a harmonised cross-system schema, calibrated, with an abstain path and an unseen-fault path. Evaluated leave-one-system-out. |
| `forecast/` | prototype predict.py | Theil-Sen/Huber trend with prediction intervals. Used only for gradual memory/disk growth; never claimed for sudden crashes. |
| `rca/` | PyRCA HT (residual on parents, healthy-only fit), RCAEval BARO, dependency topology from the prototype | Ranker combining topology, signal onset time, trace errors, classifier output and deploy events. Compared against BARO and PyRCA baselines. |
| `investigate/` | holmesgpt (structured tool results, repeat-call guard), aiops-anomaly-detector (tool loop) | Typed evidence tools over metrics, logs, traces, deploy history and past incidents. Every item gets an `evidence_id`. |
| `llm/` | prototype explain.py, holmesgpt two-phase flow | Gemini, then Groq, then template fallback. Retrieval over reviewed runbooks and verified incidents. Output is pydantic-validated JSON: summary, evidence_ids, likely_cause, alternative_causes, runbook_id, missing_information. The LLM never produces or runs shell commands. |
| `policy/` | predictive-reliability-platform (YAML policies, cooldowns), sre-agent (approval gate, audit, closed-by-default approvers) | Deterministic. Modes: watch-only, ask-first, autopilot. Allow-listed runbooks and targets, risk by target type, rate limits, circuit breaker. Approval API needs a token. |
| `executor/` | aiops-anomaly-detector, HC0416 (idea only) | Docker SDK runbooks, only ones truly implemented: restart service, recreate container, roll back image tag, clear an approved temp path. Each action is audited. Nothing simulated. |
| `verify/` | HC0416 (idea only: verify with an app-level check), AIOpsLab (post-mitigation check) | Health checks plus a synthetic checkout through all four services, held over an observation window. Outcomes: recovered / partially recovered / unresolved. On failure: preserve evidence, stop repeated interventions, escalate. |
| `evaluator/` | AIOpsLab Problem pattern (inject, workload, eval, recover) | Independent runner: crash, latency, error spike, memory leak, disk fill, bad deploy, one unsupported fault, plus healthy surges as negatives. Blind-challenge mode. Scores diagnosis, detection time, time to verified recovery, failed-request %, false alerts, harmful interventions. |
| `dashboard/` | prototype UI (reused as design reference only, no JS) | Dash + Plotly over the backend REST API only. All text from one labels file. |
| `data/` | RCAEval downloaders and layout | Cleaning script for the workbook, quality report, label mapping, RCAEval loader starting with RE1 and one system. |
| `models/` | prototype (never loaded saved models) | Training scripts, artifacts with metadata (data, feature list, git commit), a loader the live system uses. |

## Data design decisions (from inspecting the workbook)

- 295 cases, 7,880 service rows. Rows within a case are not independent, so all splits are by whole case and by system.
- `role`, `is_root`, `fault_type_at_service`, `anomaly_score` and `is_deepest_anomalous` carry label or leakage risk and are excluded from classifier inputs.
- `disk_io_ratio` and `socket_ratio` are 100% empty and are dropped. Disk fields are ~99.3% missing and stay NaN.
- memory_leak, disk_filling, bad_deploy, crash and overload exist only in the `eternalai_bench` source, so a model can learn "which source" instead of "which fault". Reports state this, and cross-system claims for these classes come only from live runs of our own app.
- The stored baseline reports macro-F1 0.957 with case folds mixing systems but 0.117 to 0.585 with a system held out. Mitigations to be measured, not assumed: domain-invariant ratio features, per-service normalisation, abstention.
- 59 outcome runs are too few for RL or "optimal action" claims. Actions are chosen by the deterministic policy; outcomes are evidence, not a learned policy.
- Runtime label mapping (explicit table in `data/label_map.py`): app_error to error_spike, slow_service to latency_spike, crash to down, with the rest mapped one by one. Labels marked "keyword match - verify by reading" are excluded from training truth.

## Runtime prerequisites

Docker and Docker Compose are required for the app, executor and evaluator. They were not found on this machine at the start of Phase 0 and need installing before step 2 of the build order. Data work and models need no Docker.
