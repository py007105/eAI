# v2 plan (APPROVED SCOPE: priorities G1-G4 in the user's message of 2026-10-18; pre-registration pending)

v1 (tag `benchmark-system-v1`, 225 rows in `results/benchmark-v1/`) stays as recorded and is never replaced. v2 runs on fresh seeds and is reported beside v1 (`docs/EVALUATION_PLAN.md`, section 9). Hour estimates are mine, not measurements. The v2 plan is evaluated in a pre-registration (Amendment 4) that is committed **before any v2 data collection or rerun**.

## Items A-D (one line each)

| item | what changes | est. h | files touched | retraining / new data |
|---|---|---|---|---|
| **A** (G1) | A pending approval expires after a TTL (proposal: 120 s): the incident is escalated with its evidence preserved, and a pending approval never blocks detection of a new incident; unit tests | 2 | `eternalai/engine.py`, `eternalai/config.py`, `tests/test_approval_ttl.py` | none |
| **B** | Every incident row (and benchmark row) records top class, confidence, abstention reason, novelty distance, exceeded limit features, report provider and latency, forecasts | 2 | `eternalai/engine.py`, `eternalai/classify.py`, `scripts/run_benchmark.py`, tests | none |
| **C** (G1) | Harness operator logs every approve call's status and any exception and fails loudly; plus a reproduction that explains why it did not approve in v1 | 1.5 | `scripts/run_benchmark.py`, `scripts/diag_approver.py`, tests | none |
| **D** | The harness resets the brain's policy state (cooldowns, breakers, suppressor, open incidents) between runs through an authenticated admin call, so runs are independent | 2 | `eternalai/api.py`, `eternalai/engine.py`, `scripts/run_benchmark.py`, tests | none |

Dependent on the surge diagnosis (`docs/postmortems/surge-false-alarm-diagnosis.md`; hypotheses H1-H3 lead):

| item | what changes | est. h | files | retraining / new data |
|---|---|---|---|---|
| **E** (G2/G3b) | Fix the healthy-surge false alarms from features and data, not rules: learned healthy limits get a minimum width for near-constant features such as memory; training adds healthy-surge windows at two intensities (and a few more `orders`/`payments` crashes); no surge flag reaches the models | 6-9 incl. about 3 h of collection | `eternalai/detect.py`, `models/train_models.py`, `models/collect_runs.py`, `models/artifacts/` | **yes**: retrain on the 72 old training runs plus fresh runs from unused training-block seeds only; v1 benchmark runs are never used |

No evaluator change is planned. Surge intensity varies by choosing seeds (the evaluator draws 25 or 40 from the seed); more levels would need an evaluator change and a new approval.

## Schedule (wall-clock hours from "now" = T; plan against 48 h; system freeze in the last 14 h)

| stage | hours | T window | notes |
|---|---|---|---|
| 0. Plan, diagnosis, this schedule | 0.5 | T+0-1 | done as this commit |
| 1. G1: reproduce the missed approval, build A and C, tests | 3.5 | T+1-4.5 | stack needed for the reproduction (about 15 min of runs) |
| 2. B and D with tests | 4 | T+4.5-8.5 | code only |
| 3. Read-only surge capture at both intensities (H1-H3, H6) | 2 | T+8.5-10.5 | brain only logging; about 12 short runs plus analysis |
| 4. Pre-registration, Amendment 4 (changes, seeds via checker, arms, counts, criteria, demo rule) | 1 | T+10.5-11.5 | **committed before stage 5** |
| 5. Fresh data collection (about 40 runs) | 3 | T+11.5-14.5 | seeds from the unused training block only |
| 6. Retrain, cross-validate, freeze `models-v2` with data hashes, build, tag `benchmark-system-v2` | 3 | T+14.5-17.5 | no change after the tag |
| 7. Pre-registered evaluation: 4 arms on the same fresh seeds, about 220 runs | 11 | T+17.5-28.5 | machine time, about 2.9 min per run; the longest unattended stage |
| 8. Triage, render v1 and v2 side by side, post-mortems, docs | 5 | T+28.5-33.5 | |
| **System freeze** (no change to `eternalai/ evaluator/ app/ models/`) | | from T+34 | |
| 9. Buffer: live LLM check (key needed then), three demo rehearsals, merge, release check, tags | 14 | T+34-48 | at least 12 h buffer kept |

Stages 0-7 total about 28.5 h of the 30 h build budget; stage 7 is mostly waiting. A slip of more than 4 hours, a memory failure that stops runs, or a change needed outside A-E is a stop-and-ask trigger.

## Evaluation design (details are fixed in Amendment 4)

Arms: autopilot, ask-first, plus `threshold_restart` and `no_action` on the same fresh seeds (paired). At least 20 healthy and surge runs per EternalAI arm with varied surge intensities, and the fault scenarios too, so the evaluation shows the fix did not simply make the system less sensitive. The v2 demo rule: v2 is shown only if it meets the pre-registered criteria on the fresh seeds; otherwise the demo uses v1 with the issues stated plainly.

## Rules for retraining (G3b)

Fit only on fresh runs from unused training-block seeds (plus the original 72 training runs, which are training data and not benchmark data). The v1 benchmark runs are seen data: they are not used to train, to select thresholds or to tune. No surge flag, scenario name or injection parameter may reach a model at inference. Surge handling comes from traffic-normalised features and healthy-surge training data, not from "ignore surges" rules. No retuning after seeing v2 results; any further change is v3.

## Not in scope

Orders-crash: no fix unless a root cause is proven. No tuning to benchmark seeds.
