# Gap analysis: prototype v2 and dataset v1

## Prototype v2 (`EternalAI_prototype_v2.zip`)

What exists: detection (z-score + per-service IsolationForest on recent live data), prediction (linear trend, Holt), rule and dependency diagnosis, Gemini/Groq/template explanations, three modes, and a local benchmark of nine fault types.

Gaps found by reading the code:

| Gap | Evidence | Fix in this project |
|---|---|---|
| The brain injects faults itself, so it can know the answer | `brain/engine.py` calls a "chaos" injector and logs "Injected '<kind>' into <service>" | Independent `evaluator/` service; ground truth in a volume the brain cannot read. |
| Saved models are never loaded | no `joblib`/`pickle`/model loading anywhere in `brain/` | `models/` artifacts with metadata and a runtime loader. |
| Detectors train on live data that may already contain a fault | `detect.py` rolling buffers | Train on windows verified healthy and traffic-normalised. |
| Diagnosis is rules, not learned; no cross-system evaluation | `diagnose.py` | Classifier plus RCA ranker evaluated leave-one-system-out. |
| Benchmark ran as local processes with direct scraping, 3 to 5 runs per cell | `bench/results/summary.md` header | Real containers, Prometheus, repeated runs with spread. Prototype numbers are not reused as results. |
| Web UI is JavaScript | `brain/static/app.js` | Dash dashboard; no authored JS. |
| Verification is not a user journey | n/a | Synthetic checkout through all four services, held over a window. |

The prototype is the author's own code, so modules may be reused with adaptation.

## Dataset v1 (`EternalAI_training_dataset_v1.xlsx`)

Facts verified by pandas so far (the cleaning script in `data/` will reproduce and extend these):

- `A_cases`: 295 cases; `A_telemetry`: 7,880 service rows; 4 systems; 12 fault labels; `A_rcaeval_index`: 735 index rows (labels only).
- `disk_io_ratio`, `socket_ratio`: 100% empty. `disk_share_max`, `disk_slope_rel` columns: 99.3% missing. Missing values must stay missing.
- Label-bearing columns present in the telemetry sheet: `role`, `is_root`, `fault_type`, `fault_type_at_service`, `anomaly_score`, `is_deepest_anomalous`. Not allowed as model inputs.
- Fault labels memory_leak, disk_filling, bad_deploy, crash and overload appear only in `eternalai_bench`; db_slowdown only in petshop; network_delay only in nezha. The stored baseline itself warns this can be learned as "which dataset".
- Stored baseline: macro-F1 0.957 (case folds, systems mixed) against 0.194 / 0.440 / 0.117 / 0.585 with one system held out. Root-cause top-1 on unseen systems: 0.55 (Online Boutique), 0.00 (PetShop), 0.18 (Train Ticket). Unknown-fault detection AUROC 0.66.
- Still to inspect: the remaining sheets (knowledge base, fix catalog, alert rules, outcome runs, SMD events) and the count of "keyword match - verify by reading" labels.
