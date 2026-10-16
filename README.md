# EternalAI

A predictive cloud recovery assistant. It watches live telemetry from a four-service app (web, orders, payments, inventory), detects anomalies with ML, ranks the root-cause service, proposes or runs an approved recovery runbook, and verifies that a synthetic checkout works again. When it cannot fix something, it escalates and says so.

**Status: early build.** Nothing here is benchmarked yet. Every number that appears in this README will come from a script in the repo that you can rerun; until then there are none.

## Principles
- Faults come from an independent evaluator. EternalAI never sees the fault name, target or answer.
- Models are trained on data, loaded from saved artifacts, and evaluated by whole incident and by leaving a system out.
- Missing data stays missing.
- The LLM returns validated JSON only. It never writes or runs shell commands. Actions are allow-listed and decided by a deterministic policy.
- Only actions that are really implemented are exposed.
- Python only (FastAPI, Pydantic, Dash).

## Layout
`docs/` design and notes · `app/` four services · `loadgen/` traffic · `eternalai/` the brain · `evaluator/` fault injection and scoring · `dashboard/` Dash UI · `data/` data scripts · `models/` training and artifacts.

See `docs/ARCHITECTURE.md`, `docs/REFERENCES.md` and `docs/GAP_ANALYSIS.md`.

## Setup
```
cp .env.example .env     # optional LLM keys; works without them
```
Requires Python 3.11+, Docker with Compose.
