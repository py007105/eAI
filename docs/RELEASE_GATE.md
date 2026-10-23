# Release gate for `demo-stable-2`

Committed before any candidate was tested against it. `demo-stable-1` (commit `49155ea`) stays the fallback and is never
moved. A passing count is not feature coverage: every item below names the behaviour it must exercise.

## Candidate
- One commit of `plan-complete` (the "candidate") and the images built from it. Every result names that commit and its
  image build.
- Results from another commit or another build do not count for this candidate.

## Required items (all on the candidate commit and build)

| id | item | how | what it must exercise |
|---|---|---|---|
| G1 | full test suite | `pytest -q -p no:cacheprovider` | all pass |
| G2 | Phase 1 live check | `scripts/live_check_phase1.py` | 17/17 (rulebook, approvals, protected service, kill switch, network lockdown, Prometheus outage) |
| G3 | Phase 4a live check | `scripts/live_check_phase4a.py` | 10/10 (learn store, POST /feedback, rule bookkeeping) |
| G4 | controlled check: two close root candidates -> abstain | `scripts/live_check_controlled.py`, check C1 | on the real stack, the root margin is substituted at run time with a value above every possible gap (artifact substitution inside the running brain container; code and image unchanged). A real fault is injected. The incident must abstain with the reason "two close root candidates", and **no action may be executed** |
| G5 | controlled check: forest-only anomaly -> approval | `scripts/live_check_controlled.py`, check C2 | the detectors' learned limits are substituted at run time by empty limits, so only "down" and the joint forest score can flag. A real fault is injected. An incident whose diagnosis says `anomaly_source = forest_only` must get `needs_approval` in autopilot, with **no automatic execution**. If no forest-only incident occurs, G5 is **not met**: no promotion, and the blocker is reported |
| G6 | knowledge base on the candidate | `scripts/live_check_controlled.py`, checks K1-K2 | K1: `/status` shows the KB loaded; `GET /kb/{label}` answers for all six live labels with an entry and ranked fixes; every diagnosed incident carries `diagnosis.fix_ranking`, and the proposed runbook equals its first executable entry. K2 (controlled): with a substituted outcomes file that changes the ranking for one fault, the proposal changes accordingly, and needs approval if its risk requires it. This shows that the ranking drives the proposal. |

Labels used in the reports:
- **live, naturally occurring:** happened in a scripted fault run without any substitution;
- **controlled check:** a deliberate substitution made the condition occur. This shows the integration path works on the
  candidate. It is **not** evidence that the condition occurs naturally, nor evidence of generalisation;
- **unit-tested only:** no live run exercised it.

## Not a gate
- **Evaluation v3** (`docs/EVALUATION_V3_PLAN.md`) is reported whatever its numbers are.
- **The dataset-A classifier** (`docs/results/dataset_a_classifier.md`) is an experiment. It is not loaded by the brain,
  and its unknown threshold failed: it is never used as a safety gate.

## Standing limit
The seed-426 cpu_burn wrong-service restart (`docs/postmortems/cpu_burn_seed426.md`) is not ruled out by any item here.
