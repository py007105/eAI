# Docker schedule until the code freeze (23 Oct 2026, 20:00 IST)

One machine, one Docker daemon, shared by the main session (Claude Code, `D:\eAI\eAI-release`) and the Codex session
(`D:\eAI\eAI-codex`). The working copy of this schedule is the top of `D:\eAI\STACK_LOCK.md`; its last line is the lock
(protocol: `docs/HANDOFF_FRIEND.md` section 1.5). Kind and the Compose stack never run at the same time.
**Superseded by `docs/COORDINATION.md` section 5 (2026-10-23 evening).** Long runs are started detached from the AI session (a separate PowerShell process) so they survive a memory-pressure stop of
the session; they are resumable (finished runs are skipped).

| when (IST) | who | what | est. |
|---|---|---|---|
| Wed 21, 09:40-11:30 | main | Forecast check v3, 20 pre-registered runs (build included) | 1 h 50 |
| Wed 21, 11:30-12:15 | main | Phase 4a live check: forest-only -> approval, close candidates -> abstain, learn store, POST /feedback; tag demo-stable-2 | 45 min |
| Wed 21, 12:15-17:15 | codex | kind window 1: cluster, Prometheus, Online Boutique, driver work | 5 h |
| Wed 21, 17:15-18:45 | main | Phase 4b live check: KB + outcome-ranked fix choice (if ready; otherwise the window goes to codex) | 1 h 30 |
| Wed 21, 18:45-22:45 | codex | kind window 2 | 4 h |
| Wed 21 23:00 - Thu 22 06:00 | main (detached) | Phase 7 re-runs, plan rulebook, autopilot: 9 scenarios x 5 seeds (all fault scenarios are policy-affected: rollback and stateful recreate are high, error/latency restarts are medium, payments is protected); memory_leak with no brain x 5 (with vs without) | about 5 h |
| Thu 22, 07:00-08:00 | main | export and checksum the overnight results; Compose regression (Phase 1 live check) | 1 h |
| Thu 22, 08:00-13:00 | codex | kind window 3: scripted end-to-end check | 5 h |
| Thu 22, 13:00-14:30 | main | re-run failed Phase 7 runs; forecast v4 (only if pre-registered with new seeds) | 1 h 30 |
| Thu 22, 14:30-19:30 | codex | kind window 4: final end-to-end, hand-back of friend/phase2-k8s | 5 h |
| Thu 22, 20:00-22:00 | main | merge friend/phase2-k8s; Compose regression (Phase 1 + Phase 4 live checks); tag demo-stable-3 | 2 h |
| Thu 22 22:00 - Fri 23 06:00 | main (detached) | buffer: ask-first comparison runs (5 seeds) or Phase 7 gaps | up to 8 h |
| Fri 23, 07:00-11:00 | codex | kind window 5: kind end-to-end on the merged code (or Telegram live check if built) | 4 h |
| Fri 23, 11:00-15:00 | main | final regression: every live check | 4 h |
| Fri 23, 15:00-18:30 | main | demo rehearsal: timed 5-minute run, Reject clicked by hand, fallback recording; final tag and push | 3 h 30 |
| Fri 23, 18:30-20:00 | - | buffer; freeze at 20:00 | |

**Fit:** everything fits if nothing has to be repeated. The tight parts are the two overnight blocks (they depend on the
machine staying up with enough free RAM) and Thursday evening's merge.
**Drop order if time runs out:** (1) forecast v4, (2) Telegram, (3) ask-first comparison runs, (4) the fifth kind window.
Never dropped: the Phase 1 regression and the demo rehearsal.
