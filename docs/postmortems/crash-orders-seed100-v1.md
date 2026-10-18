# Post-mortem: crash of `orders`, seed 100, EternalAI autopilot (v1)

Written from the run's stored row only (`docs/results/benchmark_raw.jsonl`, arm `eternalai_autopilot`, scenario `crash`, seed 100,
finished 2026-10-17 21:25:52, system commit `245d3e7`). No code was touched and no container was queried. Generated skeleton:
`scripts/postmortem_extract.py --arm eternalai_autopilot --scenario crash --seed 100`.

## What happened

The evaluator killed the `orders` container. The scorer recorded: detected, injected service ranked first, **not recovered**, final status `escalated`,
26.13% failed requests over a 20.8 s observation window.

| question | answer from the log |
|---|---|
| 1. Detected? | Yes, 5.3 s after the injection. |
| 2. Classified? | The injected service was ranked first (`orders` 0.98). The cause was `insufficient_evidence` (abstained). The expected label `down` was not reported. |
| 3. Did policy allow an action? | No action was ever proposed, so the policy engine was not consulted. |
| 4. Did the executor run? | No (0 actions executed). |
| 5. Did verification fail? | Verification never ran, because there was no action. |
| 6. Evidence, no repeated attempts, clean escalation? | The incident was closed as `escalated` 7.5 s after opening, with the message "no safe automatic action: escalated to a human with evidence preserved". No action was attempted, so there were no repeated interventions. A second incident (on `web`, which fails because `orders` is down) opened 8 s after the observation window had ended, during the restore, and was still undiagnosed when the log was read. |

## Reading it

- **The escalation itself was clean**: honest report, no wrong action, nothing executed, one incident closed within 7.5 s, no repeated attempts. That is the behaviour the design promises when it cannot proceed.
- **It was still a missed recovery on a supported fault.** A crash has a runbook (`restart_service`, `recreate_container`) and the classifier was trained on crashes of every service. Abstaining here means the
  system chose not to act on a case it was built to handle. Calling this a "demo-worthy escalation" is accurate about the mechanics and would be misleading about the outcome.
- The failed-request percentage covers only the 20.8 s the run was observed. The run ended 8 s after the escalation closed, while the service was still down, so 26.13% understates what the outage would have cost.

## What the stored row cannot answer

- **Why it abstained.** Two mechanisms can produce `insufficient_evidence`: the novelty gate (the window looked unlike anything known) or the confidence threshold. The row stores neither the confidence nor the reason. The
  preserved evidence file for incident `e5267f50` (`runtime/evidence/e5267f50.json` in the `eternalai-runtime` volume) holds `confidence` and the evidence items, and is the evidence needed. It is not read
  now, because reading it means touching the live benchmark's containers; it is read after the benchmark completes.
- Whether the evidence file exists on disk (the log says it was preserved; the code path is unit-tested but this run's file has not been checked).
- Whether this is typical for crashes of `orders` specifically (the training set had one crash of `orders`; other targets had two or three). Not examined, because no other benchmark row is read yet.

## Triage

**Unclassified for now.** Candidate outcomes, decided only on the evidence above:

- **(b) system bug** if the evidence file shows a plainly "not scraped, container exited" window that was rejected by the gate or by the confidence threshold, contradicting what the model was trained on.
- **(c) design limitation** if the gate behaves as specified and `orders` crash windows are legitimately far from the training windows (one training crash on that service).
- **(a) harness artifact** is unlikely for the abstention itself (the detection and ranking were correct), but the short observation window is a measurement limitation in the harness.

## Consequence

None for v1: the result stands as recorded. Observability gap to close in v2 regardless of the class: store the classifier confidence, the abstention reason and the novelty distance in the incident row and in the runner's raw rows.

---

## Findings after the benchmark (2026-10-18; evidence file read, models replayed offline)

Sources: `results/benchmark-v1/truth_and_evidence.zip` (evidence copy, checksummed), `eternalai/classify.py`, `eternalai/engine.py`, `docs/postmortems/crash-classifier-by-target.md`, and the 225 raw rows.

**From the evidence file `evidence/e5267f50.json`:**

- `ranking`: orders 0.984, payments 0.007, web 0.005, inventory 0.004. The injected service was ranked first with high margin.
- `abstained: true`, `likely_cause: insufficient_evidence`, stored `confidence: 0.99999839`.
- `evidence`: orders container exited with code 137 (`oom_killed=False`), `up_frac=0.0`, `lat_ratio=1.88`, `web->orders` calls failing at 1.6 per second. That is the textbook picture of a crash.
- `report_meta.provider: template`; report `missing_information`: "fault pattern not seen in training".
- **Not stored:** the top class name, the abstention reason, the novelty distance. The abstain threshold in force is 0.4 (`abstain_below`, from the model metadata) and the novelty threshold is 1.0 (`gate.threshold_`).

**What can be deduced, and what cannot.** The stored confidence (0.99999839) is far above the 0.4 threshold, so the abstention was **not** the low-confidence path. By `classify.py` that leaves two mechanisms: the novelty gate (`reason = "novel"`), or a top class of `healthy`, which the engine turns into an abstention. The row does not say which. The evidence points at the novelty gate (the report text "not seen in training"
is the template's wording for any abstention, so it does not discriminate), but this is a deduction, not a record.

**Training coverage versus the benchmark** ((fault, target) pairs, from `data/runs/*.json` and the rows; full table in the triage notes below): `crash` on `orders` occurs in **1** training run and in **2** benchmark seeds (100 and 120); `crash` on `inventory` 2 and 2, `web` 2 and 1, `payments` 3 and 0. The target was therefore not absent from training.
Both benchmark orders crashes (seeds 100 and 120) abstained at the first incident; the 3 other crash runs in the autopilot arm (inventory, inventory, web) were answered `down` at the first incident.

**Offline replay (proxy, in-sample).** `docs/postmortems/crash-classifier-by-target.md` applies the frozen classifier to the training crash runs. In the 10-20 s window after injection (when the live brain diagnoses, about 7 s after the incident opens) the orders crash had the highest median novelty distance of any training crash run (0.893 against the threshold 1.0) and 1 of 5 windows was abstained as novel; every window 20 s and later was answered `down`.
That is the same direction as the benchmark behaviour, but these windows are in the models' own training data, the benchmark crash windows themselves cannot be replayed (the rows keep no feature windows), and one orders training crash is a very thin neighbourhood for a nearest-neighbour novelty gate. This supports, but does not prove, the explanation.

**Clustering of abstentions by target** (autopilot arm, supported faults; abstained incidents of any position): inventory 3 of 10 runs, orders 3 of 9, payments 2 of 5, web 2 of 6. By that count there is no clustering on `orders`. Distinguishing the *first* incident (the one that decides recovery): the only first-incident abstentions are the two orders crashes. All other abstentions are later follow-on incidents opened after a recovery, which is a separate behaviour.

**Triage: (c) design limitation** (rule R2 in `scripts/triage_nonrecoveries.py`), with these stated limits: the abstention reason was not recorded, so "novelty gate" is a deduction; the sample is two runs on one target; and a v2 that records the reason and the novelty distance would turn the deduction into a measurement. No bug in the code path was found: the ranking was right, the policy was never consulted because the classifier abstained, and the abstain path did what the design says (no action, evidence preserved, escalated).
It is still a missed recovery on a supported fault, and the design cost of the novelty gate on thinly covered targets.
