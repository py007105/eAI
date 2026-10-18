# v2 proposal (NOT APPROVED, NOT STARTED)

Status: a proposal for the user's decision. Nothing in this file has been applied. v1 (tag `benchmark-system-v1`, 225 rows in `results/benchmark-v1/`) stays as recorded and is never replaced; any v2 runs on **fresh seeds** and is reported beside v1 (`docs/EVALUATION_PLAN.md`, section 9).
Hour estimates are my estimates, not measurements.

## What v1 showed that a v2 would address (evidence in `docs/postmortems/`)

| # | finding | class | evidence |
|---|---|---|---|
| 1 | A pending approval never expires and blocks every later incident, so the ask-first arm did not measure ask-first: 42 of 45 runs were taken with detection blocked; 0 of 30 supported runs reported recovered | (b) | `ask-first-arm-stuck-incident-v1.md` |
| 2 | Why the simulated operator did not approve is unexplained (it swallows errors); the replay worked on a fresh brain | open (a?) | same, `scripts/diag_approver.py` |
| 3 | On a traffic surge the autopilot diagnosed `memory_leak` and recreated a container in 4 of 5 runs; 8 of 10 healthy runs opened an incident | (b) candidate | `autopilot-healthy-runs-v1.md` |
| 4 | Both orders crashes abstained at the first incident (autopilot), a missed recovery on a supported fault; the reason was not recorded | (c) | `crash-orders-seed100-v1.md` |
| 5 | A restart was blocked by a cooldown left over from the previous run (the brain is not reset between runs) | (a) | `benchmark-v1-triage.md` |
| 6 | Rows do not record confidence, abstention reason, novelty distance, top class, report provider or forecasts | observability gap | plan Amendments 2 and 3 |
| 7 | Recovery is self-reported; no raw probe logs exist | (c) | plan section 5 |

## Proposed scope, smallest useful first (each a SYSTEM change unless marked tooling)

| item | change | where | est. hours |
|---|---|---|---|
| A | Expire a pending approval after a fixed time (proposal: 120 s) by escalating the incident with the evidence preserved, so detection resumes; unit test | `eternalai/engine.py`, `tests/` | 1.5 |
| B | Store in every incident row: top class, confidence, abstention reason, novelty distance, report provider and latency, forecasts; carry them into the benchmark row | `eternalai/engine.py`, `scripts/run_benchmark.py` | 2 |
| C | Harness: log every approve call's status and any exception, and fail loudly if an approval is not accepted | `scripts/run_benchmark.py` | 0.5 |
| D | Harness: reset the brain's policy state (cooldowns, breakers, suppressor) between runs, or restart the brain per run, so runs are independent | `scripts/run_benchmark.py` / small API endpoint | 1.5 |
| E | Evaluator-side probe logging: store every probe's timestamp, status and latency per run, so recovery can be computed independent of the system under test | `evaluator/` | 3.5 |
| F | Investigate the surge misdiagnosis using the new logging (B); then decide: threshold, features, or more training windows. Models are retrained only if the models are the bug | `models/`, `eternalai/` | 4-8, decided after B shows the cause |
| G | More crash runs on `orders` and `payments` (training has 1 and 3), retrain, re-evaluate the novelty gate; only if B shows the orders abstentions come from the novelty gate | `models/collect_runs.py`, retrain | 2 collection + 1.5 training |

Tooling-only (no approval needed, already allowed): renderer, triage script, docs.

## Re-run cost and design

- New seeds: `--seed0 200` (seeds 200-248; below 1000 and disjoint from v1's 100-148, the training seeds, smoke seeds and the 3000+ check ranges), same 9 scenarios x 5 repetitions.
- **Minimum**: the two EternalAI arms, 90 runs at about 3 minutes each, about 4.5 hours of machine time. Their baselines would stay at v1 (not paired on the new seeds); v2 vs v1 would be unpaired and said so.
- **Full**: all five arms, 225 runs, about 11 hours, paired as in v1.
- A fresh tag (`benchmark-system-v2`), the same plan rules, a v2 amendment committed before any v2 result is read, and a side-by-side table (the renderer already supports `--raw-v2`).

## Total estimate

Items A-E plus tests and docs: about 9-10 hours of work; F and G open-ended by their nature (4-11 more hours); plus 4.5 or 11 hours of machine time waiting. A sensible first cut is A + B + C + D (about 5.5 hours of work), then the two-arm re-run, then decide on E-G from what the new logs show.

## What I need from the user

Approval (or edits) for the scope above, which arms to re-run, and whether F and G are in or out. Until then nothing in `eternalai/`, `evaluator/`, `app/`, `models/` or the benchmark configs changes.
