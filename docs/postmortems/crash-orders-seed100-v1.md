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
