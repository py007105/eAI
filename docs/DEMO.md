# Live demo script

Status: structure and talk track, v1 numbers filled from `docs/results/benchmark.md` where stated. v2 is shown only if it meets its pre-registered criteria on fresh seeds; otherwise the demo uses v1 and states the issues plainly.

> **Three findings first (benchmark v1, `docs/results/benchmark.md`; not buried, not softened):**
> 1. **The ask-first arm is invalid.** The benchmark harness handed the brain and the simulated operator the placeholder token `change-me` (an import of the config module loaded it from `.env`), so the brain refused every approval (HTTP 503) and the operator ignored the refusal; the first proposal then sat unapproved and, because a pending approval never expires, blocked all later detection (42 of 45 runs). Its 0 of 30 recoveries say nothing about ask-first operation (`docs/postmortems/ask-first-arm-stuck-incident-v1.md`). Both faults are fixed on the v2 branch and evaluated on fresh seeds.
> 2. **False alarms on healthy runs.** The autopilot opened an incident in 8 of 10 healthy runs and recreated a container in 4 of 5 traffic surges (it called a surge a memory leak). threshold_restart had 5 of 10 false alerts and prototype_rules 8 of 10 (`docs/postmortems/autopilot-healthy-runs-v1.md`).
> 3. **Recovery is self-reported.** It comes from the system's own checkout; the independent measure is the load generator's failed-request %. No independent probe logs exist.
>
> Also true: the benchmark brains were configured without LLM keys (the report provider is not recorded per run), forecasting is implemented and unit-tested but its live lead time was not demonstrated (an attempted live check was stopped by low memory, and two smoke runs ended before the resource limit), and 27 of 30 autopilot runs reporting recovery is one application, five runs per cell, scripted faults. v2 is a proposal only (`docs/V2_PROPOSAL.md`).

Rehearse the whole script once on the real stack before presenting: a step that has not been seen to work is not demo material.

**The moment to build towards:** *the service restarted, and EternalAI's own checkout passed again.* Be exact about what that is: the "proof" is the system's own synthetic checkout, i.e. self-reported. The independent measure is the load generator's failed-request %, which the evaluator reads; show that number alongside it. The benchmark brains were configured without LLM keys, but the report provider is not recorded per run, so do not say "template only" as a verified fact; before a live-LLM demo, confirm the key reaches the brain container (presence only, never print it).

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
5. When the banner appears, deliver the line: *"The service restarted, and EternalAI's own checkout passed again; the independent measure is the failed-request %."* Show **before/after**: checkout success, app error rate, web latency.
6. Click **Reveal the truth**: injected fault, target, and what EternalAI got right or wrong. Read the scorecard line for this run: the failed-request % first (independent), then detection time and the self-reported recovery time, all read off the scorecard panel for that run. For scale, v1 autopilot means over the 30 supported runs were 18.39% failed requests, 12.1 s to detect and 50.0 s to self-reported recovery (`docs/results/benchmark.md`, section 4).
   If it was wrong, say so: an honest wrong answer is part of the demo.

## 3. Autopilot and the policy engine (2 min)

- Switch to **Autopilot** and start another challenge. Contrast: the same pipeline without the approval wait. Say which actions autopilot may and may not take (low and medium risk allow-listed runbooks only; cooldown; circuit breaker after two interventions).
- Optional: show `/audit`: every action with its actor and evidence ids.

## 4. A fault it has not seen (2 min)

- Trigger the unseen fault (cpu_burn) from the evaluator (`POST :8200/runs {"scenario":"cpu_burn"}` keeps the demo honest: it was never in the training data).
- Expected behaviour: EternalAI abstains ("insufficient evidence"), proposes no action, preserves the evidence and escalates. Say plainly that it is deliberately conservative here: a threshold-and-restart script acts without diagnosing, and whether that recovers this fault is a benchmark row, the cpu_burn rows of `docs/results/benchmark.md`: self-reported recovery was 5/5 for threshold_restart, 2/5 for prototype_rules, 1/5 for the autopilot and 0/5 for the (invalid) ask-first arm, and the autopilot abstained correctly in 4 of 5 runs, not something to assert from memory.

## 5. Healthy negatives (1 min)

- Run a `traffic_surge` or `good_deploy` challenge from the evaluator. Expected: no incident. Say that false alarms on healthy changes are a measured number (v1: healthy runs with a false alert 8/10 autopilot, 5/10 threshold_restart, 8/10 prototype_rules; the autopilot recreated a container in 4 of 5 surges), not a promise.

## 6. When recovery fails (2 min)

- Show the post-mortem in `docs/postmortems/` for a real non-recovery from the benchmark: what was detected, what was decided, what was not done, what the evidence file preserved, and which triage class it got.
- Show the circuit breaker in the status bar if it has opened. Say what a human receives: the incident, the evidence, the reason it stopped.

## 7. Close (1 min)

- Numbers, each from `docs/results/benchmark.md` (v1, 30 supported runs per arm), independent measure first: failed requests 18.39% (autopilot) versus 32.17% (no action), 26.60% (threshold_restart), 26.29% (prototype_rules); self-reported recovery 27/30 versus 12/30 and 9/30; mean seconds to self-reported recovery 50.0 versus 68.2 and 69.4; healthy runs with a false alert 8/10 (autopilot), 5/10, 8/10; harmful interventions on healthy runs 4 (autopilot), 0, 0; abstention on the unseen fault 4/5 (autopilot). Say the three findings at the top of this file aloud as part of the close.
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
