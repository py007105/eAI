# Post-mortem: the ask-first arm (v1) stopped detecting after its first unapproved proposal

Facts below come from the 45 ask-first rows, the brain's `audit.jsonl` in `results/benchmark-v1/` (via the evidence copy and a read of the stopped brain container's runtime volume), the progress log, the engine source, and a diagnostic replay on non-benchmark seeds. No v1 code was changed.

## What the rows show

- 30 supported-fault runs, 0 reported recovered; pooled detection 3 of 30 runs; 0 false alerts in 10 healthy runs; top-1 root cause 1 of 30. Every `detected` run is among the first three runs of the arm (by `finished_at`): disk_fill 104 (23:16), crash 100 (23:17), bad_deploy 105 (23:20).
- bad_deploy seed 105: the brain diagnosed `bad_deploy` on `payments` and proposed `rollback_release`, verdict `needs_approval`; the row ends with the incident `awaiting_approval` and `approved_by: null`, 89 s after the proposal. The simulated operator (`scripts/run_benchmark.py::approver`) was meant to approve after 5 s.
- Every run after that, in the whole arm (`incidents_opened` 0 in all of them), is `undetected` or healthy-without-incident.
- The brain's audit log has no `human:benchmark-operator` entry during the ask-first arm; the only two such entries are from the pre-benchmark smoke test (2026-10-17 20:28 and 20:30).

## Why detection stopped (system)

`Engine.tick` opens a new incident only when `not active`, where `active` includes incidents in `open` or `awaiting_approval` (`eternalai/engine.py`). A proposal that is never approved keeps the incident `awaiting_approval`, and nothing expires it, so the brain stopped opening incidents for every later fault until the arm ended and the container was recreated for the next arm. That is a stuck incident by the plan's own wording for class (b): no expiry on a pending approval, and a pending approval blocks all detection.

## Why the approval did not happen (not established)

The v1 records cannot say. The approver swallows every HTTP error and never checks the status of the approve call, and the progress log has no approver output. Token mismatch is excluded by reading the code (the same value is passed to the brain and the approver). A **diagnostic replay** (`scripts/diag_approver.py`, non-benchmark seeds 2105, 2115, 2125, fresh ask-first brain, default token, statuses logged) approved correctly once (`rollback_release` on `payments`, `POST approve -> 200`, recovered); the other two replays produced no proposal (escalated), so there was nothing to approve. So the approver logic works on a fresh brain; why it did not approve in the benchmark remains **unexplained**. Candidates that cannot be told apart from the records: the approver thread died on an exception outside its `except (httpx.HTTPError, ValueError)`, a transient failure of `GET /approvals`, or an approve call answered with a non-200 status that was ignored.

## Triage

**(b) system bug** for the stuck incident (28 runs, rule R1), with the unexplained missed approval recorded as an open harness question that may also be class (a). Two earlier runs are classified separately: crash 100 (abstained on orders; (c)) and disk_fill 104 (abstained; (c), reason not recorded).

## Consequence for the reported numbers

The ask-first arm in v1 **does not measure ask-first operation**: 42 of its 45 runs were taken with the brain unable to open incidents. The numbers stay in the tables as recorded (no run dropped). Statements about "ask-first" performance must not be drawn from them; the autopilot arm is the only EternalAI arm that measures the pipeline. A fix (expiry or escalation of a pending approval; approver error logging) is a system change and so a v2 on fresh seeds, reported beside v1 after approval.
