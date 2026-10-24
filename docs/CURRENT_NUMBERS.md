# CURRENT NUMBERS (for the pitch), Sat 24 Oct 2026, 16:30 IST

**Measured on candidate `71eb2f5`. Demo runs `demo-stable-1` (`49155ea`).**
`demo-stable-1` has the Phase 1 safety work: rulebook, approvals, protected payments, kill switch, hourly cap, cooldown. It does **not** have the later features in `71eb2f5`:
- forecast on every tick (`d084b20`);
- forest-only → approval (`18a4b38`);
- close root candidates → abstain (`d1c710d`, margin `65dd9fe`);
- learn store and `/feedback` (`84a3094`);
- knowledge base and outcome-ranked fix choice (`e4dc6f5`, `bed1538`).

On `demo-stable-1`, fixes come from the fixed table, and the forecast runs only when no incident is open.

Every number below comes from a committed results file or raw rows. The pooled values not printed in a report were computed from the raw rows by a script, not by hand.

- **Current policy:** `eternalai/rulebooks/default.yaml`, the plan rulebook. Autopilot runs only low-risk fixes; rollback and stateful recreate always need approval; payments is protected.
- **OLD POLICY** marks numbers measured under `eternalai/rulebooks/benchmark-v2.yaml`, where autopilot also ran rollbacks and recreates without asking. Those numbers are never pooled with current-policy numbers.
- No person approved any action in any benchmark (v1, v2 or v3).
- One application (our 4-service shop), scripted faults. Recovery is EternalAI's own checkout verification; the failed-request % comes from the load generator (independent).

## 1. Recovery with approval (main recovery number)

**v2 ask-first: 18 of 18 supported faults recovered** (OLD POLICY: benchmark-v2 system).
- **Approvals:** every action waited for approval and was then approved by a simulated operator after 5 s (`scripts/run_benchmark.py`, approver name `benchmark-operator`). No person reviewed or rejected anything, so this shows the approval path works end to end, not human judgement.
- **Current policy:** ask-first mode also requires approval for every action, so the same approval flow applies. This is my reading of the two rulebooks, not a rerun.
- **Conditions:** 6 fault types × 3 seeds (seeds 202-424), detected 18/18. Wilson 95% interval for 18/18 is 82-100%.
- **Measurements:**
  - mean failed-request % 13.51;
  - mean detection 12.11 s;
  - median time to verified recovery 48.7 s.
- **Healthy runs, v2 ask-first arm (8 runs: 4 traffic surge + 4 good deploy):** 0 of 8 opened an incident; 0 executed an action.
- **Source:** `docs/results/benchmark_v2.md` (sections 3 and 4) and `results/benchmark-v2/rerun/benchmark_v2_evaluated.jsonl`.

**Live human approval:** shown in the kind demo (bad deploy → rollback, approved by a person at the demo). Not a benchmark number. **PENDING** until Rajat's live run is verified.

## 2. Autopilot alone under the current policy (v3, no human present)

**No human present: actions that need approval wait. In these runs they were still waiting when the run ended (19 of 30) or expired (3 of 30).**
- **Run:** evaluation v3, candidate `71eb2f5`, policy `default.yaml`.
- **Executions:** `20261024T001813-4cedc8bf` (26 runs) and resumption `20261024T150914-22eb30c0` (24 runs). The resume check is valid: original rows unchanged, no duplicates, all 50 registered cases present.
- **Approver:** none. 0 of 50 rows have an approver; the runs are "unattended autopilot" by design (`docs/EVALUATION_V3_PLAN.md`).
- **Supported faults:** 6 fault types × 5 seeds (seeds 600-649).
  - detected 30/30, mean detection 12.57 s;
  - recovered 10/30 by its own verification;
  - mean failed-request % 15.78.
- **Per fault, recovered:**
  - crash 4/5;
  - disk fill 4/5;
  - memory leak 2/5;
  - latency, error spike and bad deploy 0/5 each. Their fixes need approval under this policy (medium or high risk), so they waited.
- **Healthy runs, v3 unattended autopilot arm (10 runs: 5 traffic surge + 5 good deploy):** 0 opened an incident; 0 actions.
- **Harmful interventions:** 0 (an executed action on a non-target service) in 45 autopilot runs.
- **cpu_burn** (unseen fault, no runbook): abstained correctly in 4 of 5.
- **Memory leak with vs without EternalAI** (same 5 seeds, paired): failed-request % with unattended EternalAI 0.0, 0.0, 4.49, 5.0, 1.13; without (no brain) 0.0, 0.0, 0.0, 0.0, 0.3. Within these short runs the leak itself caused almost no failed requests, and EternalAI's restarts added some.
- **Source:** `docs/results/benchmark_v3_resume/20261024T150914-22eb30c0_combined.md`, with original and resumed parts in the same folder; rows in `results/benchmark-v3/20261024T150914-22eb30c0/`.

## 3. Autopilot under the OLD policy (reference only)
- **v2 autopilot** (OLD POLICY: autopilot also ran rollbacks and recreates without asking):
  - recovered 18/18 supported faults;
  - mean failed-request % 11.15;
  - mean detection 11.78 s.
  - **Healthy runs, v2 autopilot arm (24 runs: 12 traffic surge + 12 good deploy):** EternalAI opened an incident in 1 of 24 and executed no action. The threshold-restart baseline arm, on the same 24 seeds, opened one in 6 of 24.
  - cpu_burn abstained 2 of 3. Seed 426 restarted the wrong service, a standing limitation (`docs/postmortems/cpu_burn_seed426.md`).
  - Source: `docs/results/benchmark_v2.md`.
- **v1** (OLD POLICY, 225 runs, 5 arms): `docs/results/benchmark.md`.

## 4. Safety and live checks on candidate `71eb2f5` (current policy)
- **Phase 1 safety live check:** 17/17 PASS (approvals, protected services, kill switch, high-risk needs approval). Source: `docs/results/v3_execution_20261024T001813-4cedc8bf.md`.
- **Phase 4a live check:** 10/10 PASS. The learn store and `/feedback` are verified live. "Forest-only → approval" and "close candidates → abstain" were active but never triggered live, so they're unit-tested only. Same source.
- **Release gate G2–G7 rerun** (execution `20261024T162717-159af59f`, 16:27–17:20 IST): **FAILED, so `demo-stable-2` was NOT tagged.** The demo tag stays `demo-stable-1`.
  - **G2** Phase 1: PASS, 17/17.
  - **G3** Phase 4a: PASS, 10/10.
  - **G4** (C1, close candidates → abstain): **FAIL**. The brain abstained ("two close root candidates"), made no proposal and ran no audited action. But the check also saw Docker `create`/`start` events on web, and its rule is "no Docker action on web". The source of those events is not recorded.
  - **G5** (forest-only → approval, adaptive controlled integration stimulus): PASS, 5/5.
  - **G6** (knowledge base): **FAIL**. K1 passed. In K2 the first incident followed the re-ranked list (rollback, waited for approval, expired unapproved). Then a second memory_leak incident ran `recreate_container` under autopilot without approval, while the check requires no unapproved action. That incident had no diagnosis fields, consistent with the forecast path (not verified).
  - **G7** (restoration + unmodified smoke S1): PASS.
  - C2 is INCOMPLETE as before (no forest-only incident occurs naturally); G5 replaces it as the gate item.
  - Source: `results/executions/20261024T162717-159af59f/`.

## 5. Prediction (forecast), current system
- **Forecast check v3** (20 pre-registered runs, watch-only):
  - memory leak warned before the limit in 5/5, but the median lead was **18.3 s against the 30 s target: FAILED**;
  - gradual disk fill warned in 5/5 with a median lead of **86.4 s: PASSED**;
  - 0 warnings in 10 healthy runs; 0 wrong-service warnings;
  - the stated time-to-limit window held the actual time in 0 of 10 runs.
  - Source: `docs/results/forecast_check.md`.

## 6. Models and offline results (not live)
- **Root-cause abstain margin:** 0.1215, from 316 out-of-fold training incidents. It would make 1 of 7 wrong-root incidents abstain, and 4 of 309 correctly ranked ones. Source: `docs/results/root_margin.md`.
- **Public-dataset classifier (dataset A, offline, one run): NOT the model the demo uses.**
  - **Model:** a gradient-boosting classifier trained by `models/train_dataset_a.py` on the owner's workbook, real rows only.
  - **Test set:** Train Ticket, a system never seen in training; 53 test incidents under the plan's truth definition.
  - **Result:** macro-F1 0.385 (plan feature list, variant P) and 0.449 (live-computable features, variant L). The majority-class baseline scores 0.132. The unknown-fault threshold does **not** separate unknown faults.
  - **The demo** uses the live classifier, trained on our shop's own runs (10 s live windows). On these 53 Train Ticket incidents it abstains on all 53. That's not a fair comparison: most of its inputs are missing there.
  - Source: `docs/results/dataset_a_classifier.md`.
- **The plan's figures, 58% (v1) and 54-65% over 6 seeds (v2) on Train Ticket**, are a different measurement and are not changed here. They come from the owner's plan (`docs/ETERNALAI_PLAN.md`), trained on the plan's balanced v2 files, which include synthetic rows. Those files are not on this machine, so those figures were not reproduced; 0.385 / 0.449 is real rows only.
- **NAB anomaly benchmark (offline, public data):** z-score detector recall 0.367 (11 of 30 windows), precision 0.174, 1.15 false alarms per day. Source: `docs/results/nab_detector_eval.md`.
- **LLM reports, live (5 incidents):** 0 of 5 answered and schema-valid (timeouts). The deterministic template report and fix were used every time, and all 5 recovered. Source: `docs/results/llm_live.md`.
- **Independence:** no v3 seed was used to train a model, build the knowledge base or pick a threshold. Source: `docs/results/eval_independence.md`.

## Limitations for the demo
- **Memory leak:** not used as a live demo (failed requests higher with EternalAI than without).
- **Demo faults for autopilot:** crash and disk. Their fixes are low-risk and run without approval under the current policy.
- One application, scripted faults; recovery is self-verified; seed-426 wrong-service restart; forecast memory lead FAILED.
- **G4 and G6 failed on `71eb2f5`; `demo-stable-2` not tagged.**
  - **G4 (close candidates → abstain):** the brain abstained with no proposal and no audited action. But Docker `create`/`start` events on web fell inside the check window, and their actor was not recorded. Most likely the evaluator's restore, which recreates web right after the run ends; this is not verified.
  - **G6 (knowledge base):** after the re-ranked rollback waited and expired, a forecast-path incident ran `recreate_container` on web under autopilot. The rulebook allows that without approval (low risk on web), so this is not a safety bug. But the forecast path uses the fixed fix table, not the knowledge-base ranking. Neither feature is in `demo-stable-1`.

## Roadmap (not run)
- A scripted-approver arm for v3 (the existing `eternalai_ask_first` arm with `--approve-after`). Roadmap only, not tonight.
- Retry with the second fix: implemented, **tests only**.
- Kubernetes: no live pass yet (14:14 kind run failed during monitoring setup).
- Telegram: tests only.
