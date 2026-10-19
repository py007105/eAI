# Live demo script

Status: **final, v2** (rule P of Amendment 4: all seven pre-registered criteria passed, so the demo shows v2). Rehearsed four ways on 2026-10-19 (R1 headless with the LLM, R2 with the keys removed, R3 by the presenter in a real browser, R3b automated in the real dashboard); every rehearsal, including what went wrong, is in `docs/results/demo_rehearsals.md`. Every v2 caveat is in one place: `docs/EVALUATION.md`, section "Canonical methodology, results and limitations: benchmark v2".

v2 is "fixes for the failures v1 exposed, tested on fresh seeds", not "the model is better". Say this once, early.

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

**If a judge picks an unseen fault while the autopilot is on (honest answer):** "The autopilot may abstain, escalate and keep the evidence, which is what it did in 2/3 of our v2 runs and 4/5 of our v1 runs of one unseen fault type. It may also act on the wrong service, which it did once in v2 (seed 426). We did not measure how often on other faults, and we do not claim it knows when to stop. For an unseen fault, switch to ask-first so a human sees the proposed service and runbook before anything runs. On screen a human sees the proposed service and runbook, the ranked-causes chart with its margin, and which services the map shows as anomalous. In our rehearsals the unseen fault was abstained on both times, so we have never seen a wrong-target proposal on the dashboard and we do not claim a human would spot one."
<!-- /gen:demo_v2 -->

**The moment to build towards:** *the service restarted, and EternalAI's own checkout passed again.* Be exact: the banner says "Verified by EternalAI's own synthetic checkout", an internal verification (the tagline is "Detect. Diagnose. Recover. Verify."; the old "Predict. … Prove." is kept only in `docs/screenshots/tagline_default_with_forecast_caveat_header.png` for reference). The independent measure is the load generator's failed-request %, which the evaluator reads; say it is an impact metric, not proof.

> **Never click the dashboard's "Start blind challenge" button. Start every challenge with `python scripts\demo_challenge.py start` (or `start --unseen`).** The button draws from all nine scenarios including the unseen fault, and in ask-first mode a proposal waits 120 s for approval and then expires (rehearsal R3: a disk_fill run started by the button was never approved and ended unrecovered). The script draws only from the six supported faults and the two healthy scenarios; the dashboard still shows everything.

## 0. Startup (exact procedure, as rehearsed)

1. `.env` in the checkout you demo from (`D:\eAI\eAI-release`) holds `GEMINI_API_KEY` and `ETERNALAI_APPROVAL_TOKEN` (a real secret, typed by hand; never `change-me`). Never print or commit `.env`.
2. Memory checklist (section 0b) first.
3. PowerShell window A:
   ```
   cd D:\eAI\eAI-release
   $env:PATH = "D:\eAI\eAI-workspace\eAI\.venv\Scripts;C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH
   python scripts\memguard.py
   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -ConfirmReset -ExportDir results/demo-export/live
   ```
   The launcher refuses while a benchmark process runs, exports the scorecard with checksums, resets only the scorecard volume, rebuilds the dashboard image, starts the stack under T3 (trace exporter off, no Jaeger) with the dashboard on and `gemini-3.5-flash-lite` for reports, restocks the inventory, and runs the preflight. Wait for **8 PASS lines** (about 90 s). Any FAIL: do not demo; see the fallback plan.
4. PowerShell window B: the same `cd` and `$env:PATH` lines. This is where challenges are started and revealed.
5. Browser: http://localhost:8050. Type the token **by hand** into the token field (a pasted value with extra text is refused: "invalid approval token" or "Token contains invalid characters"). Choose **Ask first**; no message under the selector means it worked.
6. Before the export is touched by any reset, the frozen benchmark checksums must verify: `results/benchmark-v2/SHA256SUMS` and `SHA256SUMS-rerun` (0 mismatches in every rehearsal).

7. Incidents opened while no challenge was running stay in the dashboard until a challenge opens a newer one (before R4: three, all "insufficient evidence", abstained, escalated, no action, cause unverified; `docs/results/idle_incidents_pre_R4.md`, which also gives a read-only command to list incidents with id and opening time). They are not fault detections.
8. The approval token cannot be checked by a non-mutating call: the brain has no authenticated read endpoint, and the preflight only checks that a non-placeholder token is set. Your token is confirmed when **Ask first** is selected with your token and no message appears under the selector.

## 0b. Demo-day memory checklist (16.8 GB machine; the rehearsals ran with 1.55 to 3.4 GB free)

1. **Close everything except Docker Desktop and the one browser window for the dashboard.** No IDE, no second browser profile, no chat or video apps, no other Docker projects.
2. **Close the Claude Code CLI session during the actual demo.** It and its background tools use memory, and a background-task reaper kills idle jobs when host RAM is low.
3. **Free-RAM check before starting:** `python scripts\memguard.py`. Start only above 2 GB free; below that, close more apps first.
4. After the 8 PASS lines, run `python scripts\stock_gate.py --check` once more right before presenting.
5. Do not run the launcher during the presentation (a restart takes about 90 s).
6. If free RAM drops below 1 GB or Docker stops, go to the fallback plan (recording and results tables).

## 1. Recommended 5-minute sequence (UI and commands)

| min | do (UI / window B) | say |
|---|---|---|
| 0:00-0:40 | Dashboard: point at the four green nodes, the mode pill "ask-first", "Models loaded from saved artifacts". | "EternalAI watches a four-service shop, diagnoses with trained models, acts only through four allow-listed runbooks under a policy, and checks the user journey before it calls anything recovered. The faults come from an independent evaluator we wrote; the truth is hidden from the system." |
| 0:40-2:40 | Window B: `python scripts\demo_challenge.py start`. The evaluator waits 45 s before injecting (200 s if the previous run changed the release); that wait is not part of detection, proposal, approval or recovery time. After the injection the map turns amber and the Approval queue card appears (R3b: at least 12.3 s and at least 18.6 s after injection; these are lower bounds, not exact measurements). Read the card aloud. Click **Approve** promptly: **the approval window is 120 s**, after which the proposal expires unexecuted. Wait for the green banner (30.0 s after the click in R3b). Then `python scripts\demo_challenge.py reveal <RUN_ID>`. | At the card: "It proposes `<runbook> → <service>`, low risk, and shows its ranked causes with the margin. A human decides. A proposal waits 120 seconds for approval and then expires, so I approve it now." At the banner: "EternalAI's own checkout passed again. The independent number is the failed-request percentage, which the evaluator measured." At the reveal: read the scenario and target, then failed-request %. If it was wrong, say so. If the draw was healthy: "No incident is the correct outcome for a healthy change." |
| 2:40-3:50 | Window B: `python scripts\demo_challenge.py start --unseen` (still Ask first). Show the report panel and causes chart. If a card appears, click **Reject**. | Read the unseen-fault narration in the numbers block above, including seed 426. "It abstained here / it proposed X; we do not claim it abstains on unseen faults." |
| 3:50-4:30 | Point at the numbers block (or `docs/results/benchmark_v2.md`). | Quote the table with the caveats in its third column. |
| 4:30-5:00 | Close. | "One application, scripted faults, three runs per fault type, recovery checked by the system itself, no paired baseline on faults, forecast lead time not demonstrated, Groq untested. Everything is reproducible from the scripts in the repository." |

Autopilot is not switched on in the live 5 minutes: the rehearsals show it works (R1, R2), but one wrong-service restart on an unseen fault (seed 426) is the honest reason to demo ask-first. If a judge asks for autopilot, switch the mode and run `demo_challenge.py start`; use the honest answer in the numbers block if they ask for an unseen fault.

## 2. Judge-facing narration, short form

- What it is: a recovery assistant prototype for one application, with ML for detection, diagnosis and root-cause ranking, deterministic policy and runbooks, and a synthetic-checkout verification.
- What is measured: the v2 numbers block, from scripts, with sample sizes; v1 and v2 are unpaired; v2 is "fixes for the failures v1 exposed, tested on fresh seeds".
- What it does not claim: production readiness, generalisation to other applications, reliable abstention on unseen faults, superiority over a restart script on faults (no paired v2 baseline), forecast lead time.
- Approval: "In ask-first a proposal waits 120 seconds for a human and then expires without running; I approve promptly." (Rehearsal R3: a proposal nobody approved expired and that run ended unrecovered.)
- The LLM only writes the report text; it never chooses or runs an action (code-path analysis, 12 isolation tests, ten live incidents; `docs/results/llm_live.md`).

## 3. Failure contingency plan

| if | do |
|---|---|
| free RAM < 1 GB, Docker stops, or the launcher shows a FAIL | stop the live part. Show the **screen recording of the rehearsal pass (R4)** and the results tables (`docs/results/benchmark_v2.md`, `docs/results/demo_rehearsals.md`, the R3b screenshots in `docs/screenshots/r3b_*.png`; `docs/screenshots/final_banner_fixture.png` is rendered from test data, not a live result, and must be called that). Say plainly that the live stack failed. Do not improvise numbers. |
| the dashboard does not update | refresh the page; `GET http://localhost:8000/status`; "Backend offline" means the brain is down: `docker compose -p eai up -d eternalai` in window A |
| no card about 75 s after `start` (about 4 min if the previous run was a deploy or rollback: the evaluator's settle wait is 45 s or 200 s before injection) | the draw was probably healthy: wait for the run to finish (60 s after injection), reveal, start again |
| "invalid approval token" / "Token contains invalid characters" | clear the token field and retype it by hand |
| a card expires (120 s) before Approve | say so; reveal; start another challenge |
| checkouts fail with HTTP 409 | the inventory stock ran out: `python scripts\stock_gate.py --restock --force` |
| a challenge hangs | `GET http://localhost:8200/runs/<id>/status`; wait up to 3 min for the evaluator to restore the stack |
| a service is stuck after a failed run | `docker compose -p eai up -d --force-recreate <service>` |
| the LLM is slow or down | nothing to do: the template report is used and recovery is unaffected (R2) |

Never `docker compose down -v` and never delete a volume by hand; the export in `results/benchmark-v2/` is the evidence.

## 4. Final readiness checklist

- [ ] frozen export checksums verify (0 mismatches)
- [ ] memory checklist done; free RAM above 2 GB
- [ ] launcher: 8 PASS lines; stock check passes
- [ ] token typed by hand; Ask first set with no error message
- [ ] window B ready with `scripts\demo_challenge.py`
- [ ] recording of the R4 pass available offline as the fallback
- [ ] `docs/results/benchmark_v2.md` and `docs/results/demo_rehearsals.md` open in a second tab
- [ ] never the "Start blind challenge" button
