# Reference repositories

Cloned shallow into `eAI-workspace/references/` (read-only, never committed here). "Real" means verified by reading source, not README. Commit hashes are the shallow-clone HEAD at study time. Where no LICENSE file exists, we take ideas only and copy no code.

| Repo | Licence | Commit |
|---|---|---|
| k-shevtsov/aiops-anomaly-detector | none (ideas only) | 1c98027 |
| microsoft/AIOpsLab | MIT | ccf08d0 |
| phamquiluan/RCAEval | MIT (some bundled baselines differ, see below) | 259ea41 |
| salesforce/PyRCA | BSD-3-Clause | 411310d |
| HolmesGPT/holmesgpt | Apache-2.0 | 2b9140c |
| suhasramanand/predictive-reliability-platform | MIT | ae0ecf6 |
| HC0416/Self_Healing_Agent__For_Microservice | none (ideas only) | 2c9c11e |
| langchain-samples/sre-agent | MIT | eee1cf0 |
| dakshsawhneyy/AIOps-Driven-Auto-Healing-SRE-System | none (ideas only) | a2bbada |
| open-telemetry/opentelemetry-demo, KubeHeal | optional, not cloned | n/a |

HC0416 was cloned with `--recurse-submodules`; `git submodule status` reported no submodules in the shallow checkout. The DeepTraLog / train-ticket submodules referenced by its code are external repos we did not fetch.

Only the three-group source reading described below was done; nothing was executed, and benchmark numbers claimed by any README were not reproduced.

## aiops-anomaly-detector (no licence)
- **Real:** IsolationForest on 5 features with a 5th-percentile score threshold (`src/model.py`); Prometheus collector for one hardcoded service; Claude tool-use agent with 4 tools and a structured `AgentResult` (`src/agent.py`); k8s rollout restart with a 900 s cooldown (`src/healer.py`); incident retrieval store (`src/rag.py`).
- **Not backed:** "detects 2-3 min earlier than Alertmanager" (no benchmark); prompt ablation numbers (no script produces them). No dataset, no fault injection.
- **Take (idea):** detect, then tool-using investigation, then guarded action; dynamic percentile threshold; incident-store interface; cooldown and rate limit.
- **Avoid:** zero-filling on collector errors (feeds fake normal data), autonomous restart without approval, unevidenced README claims.

## AIOpsLab (MIT)
- **Real:** Problem pattern (setup, inject, workload, agent, eval, recover); orchestrator and session trace; ~85 registered problem IDs; inject/recover fault generators (Chaos Mesh, app-level, k8s, OTel feature flags); TTD, exact/subset localisation, post-mitigation health check.
- **Not backed / caveats:** `aiopslab-applications` submodule is empty; needs a live k8s cluster plus Chaos Mesh; no published scores in code. Detection is scored only yes/no.
- **Take (pattern, MIT):** the evaluator's inject/recover pair per fault, session trace logging, and metrics TTD / localisation / mitigation. Re-implemented on Docker, not k8s.
- **Avoid:** k8s/Chaos Mesh/ELK weight, vendored Helm charts.

## RCAEval (MIT)
- **Real:** ~20 RCA methods in `RCAEval/e2e/` (BARO, CIRCA, RCD, MicroCause, PageRank/random-walk variants...); `Evaluator` with Avg@k and Acc@k; downloaders for RE1 (375 cases, metrics, ~390 MB), RE2 (270 cases, metrics+logs+traces, ~4.2 GB), RE3 (90 cases, code-level faults, ~534 MB). Case layout: `data.csv` (time + one column per metric) and `inject_time.txt`.
- **Caveats:** README file layout differs from what `main.py` reads (`data.csv`); CausalRCA and RUN carry no licence, CIRCA/E-Diagnosis BSD-3, MicroCause Apache-2; TORAI/RCD need Python 3.8; the `@rca` decorator silently falls back to unranked columns on crash. RCAEval methods assume the fault time is known.
- **Take:** BARO-style robust z-score ranking as baseline (d) and cheap ranker feature; Acc@k evaluation; RE1 first (smallest); the `--tdelta` idea to simulate detection delay.
- **Avoid:** full-dataset downloads (ask first), vendored `lib/`, unlicensed baselines.

## PyRCA (BSD-3)
- **Real:** five analyzers (`epsilon_diagnosis`, `bayesian`, `random_walk`, `rcd`, `ht`); causal graph learning (PC, GES, FGES, LiNGAM); metric-only (README says traces/logs are future work). HT: per-node regressors trained on normal data, standardised residual scores, optional descendant adjustment, returns top-k plus graph paths.
- **Take:** HT-style "regress node on its parents using healthy data only, score by residual" with our known service topology as the graph; output contract of ranked nodes + path + score. Baseline (d) via the `sfr-pyrca` package.
- **Avoid:** bundled thirdparty (pytetrad needs Java), heavy causal discovery on short windows. It is post-hoc, not predictive.

## holmesgpt (Apache-2.0)
- **Real:** tool-calling loop (`core/tool_calling_llm.py`) with a step cap, forced final answer, parallel tools; `StructuredToolResult` envelope; per-tool `requires_approval`; pause/resume approval flow with signed tokens; repeat-call safeguards; two-phase investigate-then-structure flow.
- **Not present:** no quantitative ranking; RCA quality is wholly the LLM.
- **Take (pattern):** structured tool-result envelope, repeat-call guard, two-phase flow. We re-implement.
- **Avoid:** its size (1.6k-line loop file, Robusta coupling) and any shell executor; we never let the LLM run commands.

## predictive-reliability-platform (MIT)
- **Real:** YAML policy engine with cooldowns and action history; z-score + IsolationForest + Prophet anomaly service; Groq RCA endpoints; `restart_container` via Docker SDK.
- **Simulated or broken:** `scale_service()` only logs and returns True ("simulated") yet is recorded as completed; `alert` is a log line; Terraform/k8s dirs in README do not exist; no post-action verification; several action endpoints index pydantic objects like dicts and would fail; substring-matched policy conditions.
- **Take:** policy YAML + cooldown + history pattern (re-implemented), compose stack shape (Prometheus/Loki/Jaeger).
- **Avoid:** simulated actions marked completed, docker.sock behind an unauthenticated API, substring conditions.

## Self_Healing_Agent__For_Microservice (no licence)
- **Real:** the pipeline lives in `src/UI/backend/`: `dynamic_healer.py` (SkyWalking traces, GGNN+Deep SVDD scoring, REINFORCE policy over restart/scale/reroute/rollback) and `recovery_executor.py` (real Docker actions, post-action HTTP health check, MTTR, backup-container reroute). Fault injector with real container pause/memory cap.
- **Claimed or fake:** `main.py` is only an injection demo; `functions/sh_actions.py` is dead code; `mock_monitor.py` is simulated; ROLLBACK is manual-only; F4 packet loss only prints "Run Clumsy"; a model file referenced in `main.py` is missing; Windows-only tooling.
- **Take (idea only):** detect, choose, execute, verify with an app-level check and MTTR; chaos injection that labels data; safe-by-default config.
- **Avoid:** copying code, single-benchmark GNN/RL, binary weights.

## sre-agent (MIT, langchain-samples)
- **Real:** read-only analyzer with subagents plus a separate `change_executor` interrupting before write tools; `/api/approve` and `/api/audit`; approver allow-list; durable checkpointer so approvals survive restart; batch approval with a size cap; pydantic `Finding`/`HealthReport` with stable identity fields for dedupe; split read/write RBAC.
- **Weak:** approve endpoint unauthenticated and an empty approver list means anyone can approve (README admits it); k8s-only; diagnosis is LLM-only; we did not trace whether the interrupt fires on every write path.
- **Take (pattern):** read/write separation, stable finding fingerprints, audit log, approval queue persisted in a DB. Our approval API requires a token and defaults closed.
- **Avoid:** open-by-default approvals, LangGraph/Slack coupling.

## AIOps-Driven-Auto-Healing-SRE-System (no licence)
- **Real:** small Lambda/Terraform glue: per-metric IsolationForest from S3, SNS to a fixed metric-to-action map, FastAPI controller using the k8s client with an API key, chaos labeller for training windows.
- **Not backed:** "severity scoring/classification" (severity is the constant "high"); "pod restart" chaos has no injector; no tests; no verification.
- **Weak design:** model sees one scalar per call, fails open (returns normal if the model fails to load), non-idempotent actions (fixed replica count, deletes the first pod), no cooldown.
- **Take (idea):** chaos-generated labelled windows to train per-signal IsolationForests.
- **Avoid:** hardcoded action map, fail-open prediction, committed layer/zip artifacts.
