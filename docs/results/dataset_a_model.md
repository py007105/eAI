# Offline Dataset-A Fault Classifier Report

> **STATUS: OFFLINE REPORT ONLY. This model is NOT used live by EternalAI.**
> The live system runs the calibrated models trained on live stack telemetry (`models/artifacts/`),
> documented in `docs/results/models_cv_v2.md` and benchmarked in `docs/results/benchmark_v2.md`.

> **Integrator labels, 24 Oct 2026** (numbers below unchanged; a rerun of `models/eval_dataset_a.py` rewrites this file without these labels):
> - The **0.564 / 0.376** below are a **separate experiment with 369 synthetic training rows; not comparable** with the real-rows-only classifier in `docs/results/dataset_a_classifier.md` (0.385 plan features / 0.449 live-computable features). The two differ in model, training data and averaging. No claim is made that synthetic rows improved accuracy.
> - 0.564 averages over the test's truth classes; **0.376 is the strict value** (predictions outside the truth classes count). Pitch documents use the strict value for this experiment, and do not compare it with a majority baseline computed another way.
> - The 50.0 % unknown-fault result: **the threshold does not separate unknown faults reliably** (39.6 % of known test cases were also flagged unknown).

## 1. Setup and Dataset Split

- **Script**: `models/eval_dataset_a.py` (fixed random seed = 42).
- **Dataset Path**: `D:\eAI\plan_dataset\` (v2 CSVs outside git).
- **Features used (33)**: `lat_ratio, lat_z, lat_slope_rel, err_base, err_fault, err_delta, rps_ratio, rps_z, cpu_ratio, cpu_z, cpu_share_max, cpu_slope_rel, mem_ratio, mem_z, mem_share_max, mem_slope_share_per_min, net_rx_ratio, net_tx_ratio, disk_share_max, disk_slope_share_per_min, up_frac, sys_lat_ratio, sys_err_delta, client_lat_ratio, client_lat_z, callers_client_lat_max_ratio, anomaly_score, n_callees, n_callers, n_callees_anomalous, n_callers_anomalous, is_deepest_anomalous, depth_from_entry`.
- **Excluded columns**: identifiers, source, system, case_ids, splits, synthetic flags, and all labels.

| Split | File | Cases / Rows | Nature | Description |
|---|---|---|---|---|
| Training | `train_balanced.csv` | 550 rows | 181 real + 369 synthetic | 11 classes balanced to 50 rows each via SMOTE & jitter |
| Validation | `val_real.csv` | 43 rows | 100% real | Used ONLY to choose the 'unknown' confidence threshold |
| Unseen System Test | `test_unseen_system_real.csv` | 53 rows | 100% real | Never-seen system (`train_ticket`), evaluated exactly once |
| Unknown Fault Test | `test_unknown_fault_real.csv` | 18 rows | 100% real | Unseen fault type (`logic_bug`), never in training |

## 2. Threshold Selection (Validation Only)

- **Validation Accuracy**: 0.930 (macro-F1: 0.960).
- **Unknown Confidence Threshold**: **0.9840** (10th percentile of top-class probability on correctly classified validation cases).

## 3. Results on Held-out Real Data

### Unseen System Test (`test_unseen_system_real.csv` - Train Ticket)

- **Balanced Accuracy**: **58.55%** (0.5855)
- **Macro-F1 (over test ground-truth classes)**: **0.564** (56.4%)
- **Macro-F1 (penalizing out-of-truth predictions)**: **0.376**
- **Known test cases flagged unknown**: **39.6%** (21 of 53)

### Confusion Matrix (rows = true class, columns = predicted class)

| True Class \ Predicted | app_error | cpu_runaway | network_delay | normal | overload | slow_service | Total |
|---|---|---|---|---|---|---|---|
| **app_error** | 0 | 0 | 7 | 4 | 0 | 2 | 13 |
| **cpu_runaway** | 0 | 5 | 0 | 1 | 1 | 0 | 7 |
| **network_delay** | 0 | 0 | 11 | 0 | 0 | 3 | 14 |
| **normal** | 0 | 1 | 0 | 16 | 0 | 2 | 19 |

### Unknown Fault Test (`test_unknown_fault_real.csv` - `logic_bug`)

- **Share flagged unknown**: **50.0%** (9 of 18 correctly flagged below threshold).

## 4. Current Live Model vs Offline Dataset-A Model

The table below places the offline Dataset-A model numbers beside the current published numbers of the live models:

| Evaluation Track | Model | Task / Dataset | Score | Source File | Status |
|---|---|---|---|---|---|
| Offline Dataset-A | HistGradientBoosting (balanced) | Cross-system transfer (`train_ticket`, 53 cases) | Macro-F1 **0.564**, Balanced Acc **0.586** | `docs/results/dataset_a_model.md` | Offline report only (NOT live) |
| Offline Dataset-A | HistGradientBoosting (threshold=0.9840) | Unknown fault abstention (`logic_bug`, 18 cases) | Flagged unknown: **50.0%** | `docs/results/dataset_a_model.md` | Offline report only (NOT live) |
| Live Application | Calibrated Gradient Boosting + IsolationForest | Live stack runs grouped CV (105 runs, 33,576 windows) | Macro-F1 **0.991**, ECE **0.003**, False alarm 1.1/100 service-min | `docs/results/models_cv_v2.md` | Offline CV of the model the demo uses (in-distribution, optimistic) |
| Public RCAEval Transfer | Gradient Boosting (leave-one-system-out) | RCAEval RE1 (3 systems, 300 incidents, 900 rows) | Mean Macro-F1 **0.616** [0.586, 0.644] (TT 0.682, SS 0.590, OB 0.575) | `docs/results/transfer_re1.md` | Offline public benchmark |
| Live Benchmark v2 | Autopilot (policy + runbooks) | Held-out seeds (18 supported runs, 24 healthy runs) | Recovered **18/18 [82%, 100%]** (v2 benchmark, old policy, approvals by a simulated operator; current unattended v3: 10/30 recovered alone), Healthy actions **0/24**, Failed req **11.15%** | `docs/results/benchmark_v2.md`, `docs/CURRENT_NUMBERS.md` | Verified live (old policy) |

## 5. Limitations and Discussion

1. **Few real cases**: The entire Dataset A contains only 181 real training cases across 11 fault classes; cross-system transfer relies on small sample sizes.
2. **Single-source bias**: 64% of planned fault types originate from only a single source system (Cramér's V = 72% between source and label), meaning models can easily learn source artifacts rather than generalized fault physics.
3. **Synthetic rows in training**: While synthetic oversampling (369 rows) balanced class representations to 50 rows each, it cannot create new underlying domain knowledge. This single run measured 56.4% macro-F1 over the truth classes (0.376 strict) and 58.6% balanced accuracy on Train Ticket; no general claim about cross-system generalisation is made from it.
4. **Live separation**: The live EternalAI detector and classifier operate on high-frequency 10 s rolling windows of container metrics and traces specifically calibrated for the monitored stack, where in-distribution performance reaches 0.991 macro-F1. Cross-system transfer remains a known open challenge across the AIOps literature.
