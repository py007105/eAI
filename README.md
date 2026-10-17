# EternalAI

A predictive cloud recovery assistant. It watches live telemetry from a four-service application (web, orders, payments, inventory), detects anomalies, ranks the
root-cause service, proposes or runs an approved recovery runbook, and **proves** recovery by passing a synthetic checkout through all four services over an
observation window. When it cannot fix something, it says so, keeps the evidence and stops.

> **Status: documentation draft, benchmark in progress.** This README contains no results numbers. Every number in this repository comes from a script you can
> rerun and is written to a file under `docs/results/`; this page links to them. Read `docs/EVALUATION.md` (methods and limitations) before any number.

## Quick start

```
git clone https://github.com/py007105/eAI && cd eAI
cp .env.example .env            # optional: GEMINI_API_KEY / GROQ_API_KEY; set ETERNALAI_APPROVAL_TOKEN to a real secret to enable Approve/Reject
docker compose --profile releases build
docker compose up -d
```

| what | where |
|---|---|
| dashboard | http://localhost:8050 |
| EternalAI API | http://localhost:8000 (`/status`, `/incidents`, `/approvals`) |
| the shop (web service) | http://localhost:8080 |
| evaluator (fault injection and scoring) | http://localhost:8200 |
| Prometheus / Jaeger | http://localhost:9090 / http://localhost:16686 |

Requires Docker with Compose. Python 3.11+ only for running the scripts and tests outside containers. Without an LLM key every report is a deterministic template report;
the system works the same. The approve, reject and mode endpoints are refused until `ETERNALAI_APPROVAL_TOKEN` is set to something other than the placeholder.
Stop everything with `docker compose down`.

## What it does

1. **Observe**: Prometheus metrics, container state and logs of the four services (real FastAPI apps with real state, metrics and traces; versioned images so rollback is real).
2. **Detect**: per-service healthy-range limits and an IsolationForest on traffic-normalised features; a service that is not being scraped is treated as anomalous, never as normal.
3. **Diagnose**: a root-cause ranker over the service graph, a fault classifier with calibrated probability, and an explicit abstain path including a novelty gate for faults it has not seen.
4. **Act under policy**: three modes (watch-only, ask-first, autopilot), an allow-list of four real runbooks (restart, recreate, roll back to the previous release, clear an approved temp path),
   risk by target, cooldowns and a circuit breaker. Decisions are deterministic.
5. **Verify**: a synthetic checkout through web, orders, inventory and payments, held over a window. Only then is an incident marked recovered; otherwise it is partially recovered or unresolved.
6. **Escalate honestly**: on failure or abstention it preserves the evidence, stops repeated interventions and hands over.
7. **Report**: a Gemini (primary), Groq (secondary) or template report, constrained to a strict JSON schema. The model never writes or runs commands.

## Safety properties (each is enforced in code and covered by a test)

- Faults come from an independent evaluator; the ground truth lives in a volume the brain does not mount, and is revealed only after scoring.
- The LLM cannot act: its output is validated, evidence ids must exist, the runbook must be one the deterministic table allows for the diagnosed cause, and the engine's own diagnosis stays authoritative.
- Only implemented actions are exposed; nothing is simulated and presented as real.
- Splits for every model evaluation are by whole run, incident or system; preprocessing and thresholds are fitted on training folds only.
- Missing data stays missing; label-bearing fields are excluded from model inputs.

## Results

None are stated here. See:

- `docs/EVALUATION.md` (methods, limitations, how to reproduce) and `docs/EVALUATION_PLAN.md` (the benchmark rules, fixed before results)
- `docs/results/` (generated tables: public-dataset, own-application and cross-system results are kept separate; `benchmark.md` appears when the benchmark has finished)
- `docs/MODEL_CARD.md`, `docs/DATA.md`, `docs/DATA_QUALITY.md`, `docs/postmortems/`

## Limitations (short form; the full list is in `docs/EVALUATION.md`)

72 training runs, one application, scripted faults, laboratory public data, optimistic cross-validation scores, n = 5 per benchmark cell, recovery **self-reported** by the system's own checkout (the independent measure is the load generator's failed-request %), benchmark reports were template-only (no LLM key in the benchmark brain), the Gemini path tried only a few times and Groq untested.

## Repository layout

`app/` four services · `loadgen/` traffic · `eternalai/` the brain (features, detection, classification, ranking, forecast, policy, executor, verification, LLM, API) · `evaluator/` fault injection and scoring ·
`dashboard/` Dash UI (all text in one labels file, English and Hindi) · `data/` data scripts · `models/` training and frozen artifacts · `scripts/` benchmark, status, rendering and debugging tools · `tests/` unit and regression tests · `docs/`.

## Credits and licences

MIT licence (`LICENSE`). Patterns, not code, were taken from the reference projects listed in `docs/REFERENCES.md`; attributions and data licences are in `NOTICE`.
