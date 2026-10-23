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
| G4 | controlled check C1: two close root candidates -> abstain | `scripts/live_check_controlled.py` | **modified runtime configuration** (not the candidate's): `models/artifacts/root_margin.json` replaced inside the running brain container (margin 1.01), brain restarted; image and source unchanged. A real crash on web, through the real decision path, must abstain with "two close root candidates", make no proposal, and leave **no audited action and no Docker action on the target** |
| G5 | controlled check C2: forest-only anomaly -> approval | same | modified runtime: `models/artifacts/detectors.joblib` with the learned limits emptied. A real fault on web; an incident with `anomaly_source = forest_only` must wait for approval ("unusual combination"), with no autopilot action in the audit and no Docker action on the target. **If no forest-only incident occurs the item is INCOMPLETE, not passed: no promotion** |
| G6 | knowledge base | same | K1 (unmodified stack): `/status` shows the KB; `GET /kb/{label}` answers for all six live labels; every proposing incident in the script carries `fix_ranking` and proposes its first executable entry. K2 (modified runtime: `data/kb/outcomes_measured.csv` without the memory_leak/recreate rows): a real memory leak gets the re-ranked proposal; a high-risk one waits, with no audited or Docker action |
| G7 | restoration and unmodified smoke | same | after every controlled check, in a `finally`, the brain is recreated from the image and the three files inside it must equal this commit's (SHA256) with margin 0.121529; then S1 on the unmodified stack: a real crash on web is restarted by autopilot |

Statuses: PASS, FAIL, or INCOMPLETE. Only PASS counts. Every result file must name the candidate commit **and the execution ID** of the
run that produced it (`scripts/run_v3_sequence.py` creates a unique ID per execution and writes fresh per-execution outputs); a
file from another execution, even of the same commit, does not count.

Labels used in the reports:
- **live, naturally occurring:** happened in a scripted fault run without any substitution;
- **controlled check (modified runtime configuration):** a data file inside the running brain container was replaced so
  that the condition occurs; image and source unchanged, decision code unmodified. This shows the integration path works on the
  candidate's code. It is **not** evidence that the condition occurs naturally, nor evidence of generalisation;
- **unit-tested only:** no live run exercised it.

## Not a gate
- **Evaluation v3** (`docs/EVALUATION_V3_PLAN.md`) is reported whatever its numbers are.
- **The dataset-A classifier** (`docs/results/dataset_a_classifier.md`) is an experiment. It is not loaded by the brain,
  and its unknown threshold failed: it is never used as a safety gate.

## Standing limit
The seed-426 cpu_burn wrong-service restart (`docs/postmortems/cpu_burn_seed426.md`) is not ruled out by any item here.
