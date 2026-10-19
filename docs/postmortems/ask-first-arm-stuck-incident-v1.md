# Post-mortem: the ask-first arm (v1) stopped detecting after its first unapproved proposal

Facts below come from the 45 ask-first rows, the brain's `audit.jsonl` in `results/benchmark-v1/` (via the evidence copy and a read of the stopped brain container's runtime volume), the progress log, the engine source, and a diagnostic replay on non-benchmark seeds. No v1 code was changed.

## What the rows show

- 30 supported-fault runs, 0 reported recovered; pooled detection 3 of 30 runs; 0 false alerts in 10 healthy runs; top-1 root cause 1 of 30. Every `detected` run is among the first three runs of the arm (by `finished_at`): disk_fill 104 (23:16), crash 100 (23:17), bad_deploy 105 (23:20).
- bad_deploy seed 105: the brain diagnosed `bad_deploy` on `payments` and proposed `rollback_release`, verdict `needs_approval`; the row ends with the incident `awaiting_approval` and `approved_by: null`, 89 s after the proposal. The simulated operator (`scripts/run_benchmark.py::approver`) was meant to approve after 5 s.
- Every run after that, in the whole arm (`incidents_opened` 0 in all of them), is `undetected` or healthy-without-incident.
- The brain's audit log has no `human:benchmark-operator` entry during the ask-first arm; the only two such entries are from the pre-benchmark smoke test (2026-10-17 20:28 and 20:30).

## Why detection stopped (system)

`Engine.tick` opens a new incident only when `not active`, where `active` includes incidents in `open` or `awaiting_approval` (`eternalai/engine.py`). A proposal that is never approved keeps the incident `awaiting_approval`, and nothing expires it, so the brain stopped opening incidents for every later fault until the arm ended and the container was recreated for the next arm. That is a stuck incident by the plan's own wording for class (b): no expiry on a pending approval, and a pending approval blocks all detection.

## Why the approval did not happen (established, 2026-10-18)

**The harness gave the simulated operator, and the brain, the placeholder token `change-me`, which the brain treats as "approval API disabled" (HTTP 503); the operator ignored the 503.** Evidence, in the order it was found:

1. A brain started by the v1 harness (`run_benchmark.py --manage-stack`, reproduced twice on this machine and tree, smoke seeds 2000-2005 and 2001) had `ETERNALAI_APPROVAL_TOKEN=change-me` inside the container, and a probe approve with the benchmark token answered **HTTP 503**. A brain started with the same compose command and an explicit token (three probes: Git Bash, PowerShell, background PowerShell) had the right token.
2. Mechanism: `scripts/run_benchmark.py` imports `models/collect_runs.py`, which imports `eternalai/config.py`, which calls `load_dotenv()`. The repository's `.env` defines `ETERNALAI_APPROVAL_TOKEN=change-me` (names and the placeholder only were checked; no key value was read), so the environment variable the harness then read with `os.getenv("ETERNALAI_APPROVAL_TOKEN", "benchmark-token-not-a-secret")` was `change-me`, not the default. The harness started the brain with it and the operator sent it. Deterministic proof of the import side effect: `tests/test_run_benchmark_harness.py::test_mechanism_of_v1_importing_eternalai_config_loads_dotenv_into_the_environment`.
3. `eternalai/api.py::_auth` answers 503 ("approval API disabled") when the configured token is empty or `change-me`. The v1 operator never checked the status of its approve call and swallowed errors, so the progress log shows nothing. The brain's audit log has no `human:benchmark-operator` entry in the arm, consistent with every approve being refused.
4. Earlier replays with `scripts/diag_approver.py` approved correctly because that script does not import `eternalai.config`, so its token stayed the default. That is why the first diagnosis ("works on a fresh brain") looked like a contradiction.

What is not directly observable: the v1 ask-first brain container itself (it was recreated by later arms), so the failure on that exact container is inferred from an identical code path, `.env` and tree reproducing it, not seen on it. The first proposal in the arm (bad_deploy seed 105) is the earliest moment the missing approval could matter.

## Triage

**(a) harness artifact is the cause** (the approval token never worked, so no proposal could be approved) and a **(b) system flaw is the amplifier** (a pending approval never expires and blocks all detection): without the harness fault the arm would have worked; without the flaw one failed approval would not have blinded the brain for 42 runs. The 28 affected runs are filed as (a) with the (b) amplifier named in their evidence (rule R1). Two earlier runs are classified separately: crash 100 (abstained on orders; (c)) and disk_fill 104 (abstained; (c), reason not recorded).

## Consequence for the reported numbers

The ask-first arm in v1 **does not measure ask-first operation**: 42 of its 45 runs were taken with the brain unable to open incidents. The numbers stay in the tables as recorded (no run dropped). Statements about "ask-first" performance must not be drawn from them; the autopilot arm is the only EternalAI arm that measures the pipeline. The fixes (token no longer read from the dotenv-polluted variable, a preflight that aborts if the approval API rejects the token, approver status logging, expiry of pending approvals) are v2 items A and C, on branch `v2-dev`, evaluated on fresh seeds and reported beside v1.
