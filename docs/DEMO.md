# Live demo script

Status: structure and talk track. Numbers appear as `[[...]]` placeholders and are filled only from `docs/results/benchmark.md` after the benchmark has finished.
Rehearse the whole script once on the real stack before presenting: a step that has not been seen to work is not demo material.

**The moment to build towards:** *the service restarted, and EternalAI proved the application works again.*

## 0. Before the demo (do this on a quiet machine, 15 minutes ahead)

1. `cp .env.example .env` and set `ETERNALAI_APPROVAL_TOKEN` to a real secret (approve, reject and mode changes are refused otherwise). Optional: `GEMINI_API_KEY` for live LLM reports.
2. `docker compose --profile releases build && docker compose up -d`; wait about 60 s. Open http://localhost:8050. The status bar should show the mode and "Models loaded from saved artifacts".
3. **Reset the scorecard.** The scorecard panel aggregates every run stored in the evaluator's volume, which after development and the benchmark contains hundreds of runs that are not part of the demo.
   Copy `results.jsonl` out of the `eai_truth` volume first if the benchmark is still being written up, then `docker compose down`, `docker volume rm eai_truth`, `docker compose up -d`.
   Never do this while the benchmark is running.
4. Set the mode in the dashboard (enter the token, choose **Ask first**). Confirm `GET /status` shows no `fallbacks_in_use`.
5. Keep a terminal open on `docker compose logs -f eternalai` as a fallback view.

## 1. Introduction (1 min)

- One sentence: observe, diagnose, act under policy, **verify the user journey**, escalate honestly.
- Show the service map: four services, all green; show that traffic is flowing (loadgen) and that a checkout works: `curl -X POST localhost:8080/api/checkout ...` or the shop endpoint.
- Say what is real: real containers, real restarts and rollbacks, real metrics. Say what is controlled: the faults are injected by a script we wrote.

## 2. Blind challenge, ask-first (4-5 min)

1. Click **Start blind challenge**. State aloud: neither the presenter nor EternalAI knows what the evaluator picked; the ground truth is in a volume the brain cannot read.
2. Watch the service map turn amber or red and the failing path highlight; the incident timeline starts.
3. When a proposal appears in the **Approval queue**, read it aloud: the ranked causes, the proposed runbook, the risk, the evidence ids. Point out the margin between the top two causes and that the percentage shown is a calibrated probability (only shown because its calibration check passed).
4. Click **Approve**. Narrate: the executor runs one allow-listed runbook; then verification runs a synthetic checkout through all four services for the observation window.
5. When the banner appears, deliver the line: *"The service restarted, and EternalAI proved the application works again."* Show **before/after**: checkout success, app error rate, web latency.
6. Click **Reveal the truth**: injected fault, target, and what EternalAI got right or wrong. Read the scorecard line for this run: detection time `[[x]]` s, verified recovery `[[y]]` s, failed requests `[[z]]`%.
   If it was wrong, say so: an honest wrong answer is part of the demo.

## 3. Autopilot and the policy engine (2 min)

- Switch to **Autopilot** and start another challenge. Contrast: the same pipeline without the approval wait. Say which actions autopilot may and may not take (low and medium risk allow-listed runbooks only; cooldown; circuit breaker after two interventions).
- Optional: show `/audit`: every action with its actor and evidence ids.

## 4. A fault it has not seen (2 min)

- Trigger the unseen fault (cpu_burn) from the evaluator (`POST :8200/runs {"scenario":"cpu_burn"}` keeps the demo honest: it was never in the training data).
- Expected behaviour: EternalAI abstains ("insufficient evidence"), proposes no action, preserves the evidence and escalates. Say plainly that it is deliberately conservative here: a threshold-and-restart script acts without diagnosing, and whether that recovers this fault is a benchmark row, `[[benchmark: unseen-fault row, all arms]]`, not something to assert from memory.

## 5. Healthy negatives (1 min)

- Run a `traffic_surge` or `good_deploy` challenge from the evaluator. Expected: no incident. Say that false alarms on healthy changes are a measured number (`[[false-alert row]]`), not a promise.

## 6. When recovery fails (2 min)

- Show the post-mortem in `docs/postmortems/` for a real non-recovery from the benchmark: what was detected, what was decided, what was not done, what the evidence file preserved, and which triage class it got.
- Show the circuit breaker in the status bar if it has opened. Say what a human receives: the incident, the evidence, the reason it stopped.

## 7. Close (1 min)

- Numbers, each from the generated tables: verified recovery rate `[[ ]]` versus the baselines `[[ ]]`; time to verified recovery `[[ ]]`; failed requests `[[ ]]`%; false alerts on healthy runs `[[ ]]`; harmful interventions `[[ ]]`; abstention on the unseen fault `[[ ]]`.
- Name the limits in one breath: one application, scripted faults, n = 5 per cell, recovery judged by the system itself. Point at `docs/EVALUATION.md` and `docs/QA_FOR_JUDGES.md`.

## Fallback plan

| if | do |
|---|---|
| the dashboard does not update | refresh; check `GET :8000/status`; the dashboard caches the backend and shows "Backend offline" when it is down |
| a challenge hangs | `GET :8200/runs/<id>/status`; wait for the evaluator to restore the stack (up to 3 min after a release change) before starting another |
| approvals are refused | the token is still the placeholder; set `ETERNALAI_APPROVAL_TOKEN` in `.env` and `docker compose up -d eternalai` |
| a service is stuck after a failed run | `docker compose up -d --force-recreate <service>`; check `docker compose ps` |
| nothing works | show `docs/screenshots/` (fixture data, say so) and the generated results; do not improvise numbers |

## Reset between rehearsals

`docker compose down && docker compose up -d`. To remove demo state entirely, `docker compose down -v` (this also deletes the shop's data and the evaluator's records).
