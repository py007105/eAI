# Live demo script

Status: **v2 version** (rule P of Amendment 4: all seven pre-registered criteria passed, so the demo shows v2). Every v2 caveat is in one place: `docs/EVALUATION.md`, section "Canonical methodology, results and limitations: benchmark v2". The rehearsal results and the final startup, narration, UI and contingency sections are completed after the three rehearsals (`docs/results/demo_rehearsals.md`); until that file exists they are drafts and say so.

v2 is "fixes for the failures v1 exposed, tested on fresh seeds", not "the model is better". Say this once, early. The v1 findings that motivated v2 (invalid ask-first arm, false alarms on healthy runs, self-reported recovery) are in `docs/EVALUATION.md` and `docs/results/benchmark.md`.

<!-- gen:demo_v2 -->
**Numbers to quote (v2, filled from `docs/results/benchmark_v2.md`; caveats in `docs/EVALUATION.md`, canonical section):**

| say | value | say alongside it |
|---|---|---|
| supported faults, autopilot: recovered by its own check | 18/18 | 18 runs, 3 per fault type: "no failure observed", not a rate |
| supported faults, ask-first: recovered | 18/18 | same sample size |
| healthy runs, autopilot: incidents opened | 1/24 | the threshold-restart script on the same seeds: 6/24 |
| healthy runs, autopilot: actions executed | 0/24 | 24 runs cannot rule out a rate of several percent |
| mean detection time, autopilot | 11.78 s | v1 was 12.1 s: a tie within noise |
| mean failed-request %, autopilot (independent measure) | 11.15% | no same-seed no-action reference in v2; not comparable with v1 |
| unseen fault (cpu_burn), autopilot abstained | 2/3 in v2, 4/5 in v1 | different seeds, never pooled |

**The unseen-fault segment (labelled as such, ask-first mode):** `python scripts/demo_challenge.py start --unseen`. Say before it starts: "this is a fault type EternalAI was never trained on. In our tests it abstained in 2/3 v2 runs and 4/5 v1 runs, and in one v2 run (seed 426) it chose the wrong service: it ranked the true target 3rd, did not flag the window as novel, and restarted `inventory` while the fault was on `orders`; failed requests were 27.71% and the checkout probes 0/4. We do not claim it abstains on unseen faults. That is why this segment runs in ask-first mode: it proposes, a human decides."

**If a judge picks an unseen fault while the autopilot is on (honest answer):** "The autopilot may abstain, escalate and keep the evidence, which is what it did in 2/3 of our v2 runs and 4/5 of our v1 runs of one unseen fault type. It may also act on the wrong service, which it did once in v2 (seed 426). We did not measure how often on other faults, and we do not claim it knows when to stop. For an unseen fault, switch to ask-first so a human sees the proposed service and runbook before anything runs. What you see on screen is the proposal and the ranked services; whether that is enough for a human to spot a wrong target is recorded in the rehearsal log (`docs/results/demo_rehearsals.md`)."
<!-- /gen:demo_v2 -->

**The moment to build towards:** *the service restarted, and EternalAI's own checkout passed again.* Be exact about what that is: the "proof" is the system's own synthetic checkout (an internal verification). The independent measure is the load generator's failed-request %, which the evaluator reads; show it alongside, and say it is an impact metric, not proof.

## 0. Before the demo (startup; exact procedure in the rehearsal log once rehearsed)

1. `.env` exists with `ETERNALAI_APPROVAL_TOKEN` set to a real secret (approve, reject and mode changes are refused otherwise). Optional: `GEMINI_API_KEY` for live LLM reports. Never print or commit `.env`.
2. Verify the benchmark export before any reset: `sha256sum -c` on `results/benchmark-v2/SHA256SUMS` and `SHA256SUMS-rerun` (0 mismatches expected).
3. Start with the launcher: `powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -ConfirmReset`. It refuses while a benchmark process runs, exports and checksums first, resets only the scorecard volume (a copy is already in the export), starts the stack under telemetry condition T3 (trace exporter off, no Jaeger) **with the dashboard on**, restocks the inventory to the seeded level (the inventory service only subtracts stock), and runs `scripts/preflight.py`.
4. Open http://localhost:8050. The status bar should show the mode and "Models loaded from saved artifacts"; `GET :8000/status` must show no `fallbacks_in_use`.
5. Keep a terminal on `docker compose logs -f eternalai` as a fallback view.
6. The dashboard was not running during the evaluation; its polling is read-only. The rehearsals check that it does not change the brain's decisions (`docs/results/demo_rehearsals.md`).

## 0b. Demo-day memory checklist (the machine has 16.8 GB and the demo stack ran with only 1.5 to 2.6 GB free in the rehearsals)

1. **Close everything except Docker Desktop and the one browser window for the dashboard.** No IDE, no second browser profile, no chat or video apps, no other Docker projects.
2. **Close the Claude Code CLI session during the actual demo.** It and its background tools use memory, and a background-task reaper kills idle jobs when host RAM is low.
3. **Free-RAM check before starting:** `python scripts/memguard.py` (prints free RAM). Start only above 2 GB free; below that, close more apps first. (In the rehearsals the minimum free RAM was 1.55 GB headless, with nothing but Docker running.)
4. Start the stack with the launcher, wait for 8 PASS lines, then run `python scripts/stock_gate.py --check` once more right before presenting.
5. Do not run the launcher twice in a row during the presentation: the stack restart takes about 90 s.
6. If free RAM drops below 1 GB mid-demo or Docker stops, go to the fallback plan below (show the recording and the results tables).

> **Never click the dashboard's "Start blind challenge" button. Start every challenge with `python scripts\demo_challenge.py start` (or `start --unseen`).** The button draws from all nine scenarios including the unseen fault, and in ask-first mode a proposal it creates waits 120 s for approval and then expires (rehearsal R3: a disk_fill run started by the button was never approved and ended unrecovered). The script draws only from the six supported faults and the two healthy scenarios, and the dashboard still shows everything.

## 1. Introduction (1 min)

- One sentence: observe, diagnose, act under policy, **verify the user journey**, escalate honestly.
- Show the four services green and traffic flowing. Say what is real (containers, restarts, rollbacks, metrics) and what is controlled (the faults come from a script we wrote).

## 2. Hidden challenge, ask-first (4-5 min)

1. Start the hidden challenge: `python scripts/demo_challenge.py start`. It draws one of the six supported faults or the two healthy scenarios with `secrets` and does not print the choice. (The dashboard's own "Start blind challenge" button draws from all nine scenarios including the unseen fault; changing that would be a system change, so it is not used for the live challenge. The dashboard still shows the incident, the service map and the approval queue.)
2. Watch the service map and the incident timeline. If it is a healthy scenario, the expected outcome is **no incident**; say so.
3. When a proposal appears in the **Approval queue**, read it aloud: the ranked causes, the proposed runbook, the risk, the evidence ids, and the margin between the top two causes.
4. **Approve** (token needed). Narrate: one allow-listed runbook, then a synthetic checkout through all four services over the observation window.
5. When the verification banner appears: *"EternalAI's own checkout passed again; the independent measure is the failed-request percentage."*
6. Reveal: `python scripts/demo_challenge.py reveal RUN_ID`. Read the failed-request % first, then detection time. If it was wrong, say so.

## 3. Autopilot and the policy engine (2 min)

- Switch to **Autopilot** and start another hidden challenge. Say what autopilot may and may not do (allow-listed low and medium risk runbooks, cooldown, circuit breaker after two interventions). Optional: `/audit`.

## 4. A fault it has not seen (2 min, labelled, ask-first)

- Switch to **Ask first**, then `python scripts/demo_challenge.py start --unseen`. Use the narration in the numbers block above. The expected outcome is **uncertain by design**: abstain and escalate (as in most of our runs), or a proposal that targets the wrong service (as in seed 426). Show the ranked causes and say that if a proposal appears, a human must check it; do not approve a proposal whose service you do not believe.
- Whether the evidence on screen lets a human spot a wrong target is recorded in the rehearsal log. Until it is recorded, do not claim it.

## 5. When recovery fails (1-2 min)

- Show `docs/postmortems/cpu_burn_seed426.md` (a real wrong-service action) and the circuit breaker in the status bar if it opened.

## 6. Close (1 min)

- Quote the numbers block, each with its caveat. Name the limits in one breath: one application, scripted faults, n = 3 per fault type, recovery judged by the system itself, no paired baseline for supported faults, forecast lead time undemonstrated, Groq untested.

## Fallback plan (draft; finalised after the rehearsals)

| if | do |
|---|---|
| the dashboard does not update | refresh; check `GET :8000/status`; the dashboard shows "Backend offline" when the backend is down |
| a challenge hangs | `GET :8200/runs/<id>/status`; wait for the evaluator to restore the stack (up to 3 min after a release change) before the next |
| approvals are refused | the token is still the placeholder; set `ETERNALAI_APPROVAL_TOKEN` in `.env` and `docker compose up -d eternalai` |
| checkouts fail with HTTP 409 | the inventory stock ran out: `python scripts/stock_gate.py --restock --force` |
| a service is stuck after a failed run | `docker compose up -d --force-recreate <service>`; check `docker compose ps` |
| nothing works | show `docs/screenshots/` (fixture data, say so) and the generated results; do not improvise numbers |

## Reset between rehearsals

Use the launcher (`-ConfirmReset`) after the checksum verification. Never `docker compose down -v` and never delete a volume by hand: the export in `results/benchmark-v2/` is the evidence.

## Dashboard rehearsal under T3

Result: recorded in `docs/results/demo_rehearsals.md` (pending until the rehearsals are done).
