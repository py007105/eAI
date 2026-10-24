# Demo rehearsal on `demo-stable-1` (`49155ea`), Sat 24 Oct 2026, 18:26-18:54 IST: summary

- A demo rehearsal, not a gate and not a benchmark. Same stack as the demo, from the worktree `D:\eAI\eAI-demo-stable-1`, driven by `scripts/demo_rehearsal_ds1.py`.
- Rulebook `default.yaml`: autopilot runs low-risk fixes only; payments is protected.
- The script never approves anything. Tokens were generated per run and never printed; the approval token was written only to a file outside git and deleted when each run ended.

## Result per step (final)

| step | run | result | detection | action | approved by | wait | verified | failed-request % |
|---|---|---|---|---|---|---|---|---|
| 1. crash on web → autopilot restart | 18:26 | **PASS** | 5.3 s | `restart_service` on web (low risk, autopilot) | none needed | - | recovered (46.6 s after the crash) | 52.01 |
| 2. disk fill on web → autopilot `clear_temp_path` | 18:35 | **PASS** | 7.3 s | `clear_temp_path` on web, twice (two incidents), autopilot; **no other action without approval** | none needed | - | recovered (38.5 s after the fault) | 0.0 |
| 3. bad deploy on payments → ask-first → a person approves | 18:49 | **PASS** | 26.3 s | `rollback_release` on payments (high risk) | the owner, in the dashboard (recorded as `human:dashboard`) | **58.1 s** from proposal to approved execution | recovered (115.6 s after the bad deploy) | 14.99 |

**Step 3 conditions:**
- Approval window **300 s** (demo override `D:\eAI\demo\compose.demo-ttl300.yml`, no code change).
- The proposal was pending at 18:52:17; the rollback executed at 18:53:14, audit actor `human:dashboard`.
- This commit's dashboard always sends the approver name `dashboard`, so the name of the person who clicked is not recorded.

**Free RAM:**
- 2.59 GB with the stack up;
- 2.38 GB when the approval was pending;
- 3.71 / 3.07 / 3.06 GB before the three runs started.

## What went wrong on the way (kept as evidence)

1. **Run 18:26, step 2 FAIL and step 3 NOT APPROVED:**
   - The **kill switch was turned ON** between 18:29:31 and 18:31:07, outside the script. It's not in the audit log.
   - After startup, only `POST /killswitch` with the approval token can turn it on; the dashboard's toggle calls it, and the script never does.
   - Disk fill was diagnosed correctly (`disk_fill` on web), but `clear_temp_path` was blocked with "kill switch is on: nothing is executed". Step 3 could not get an approval in watch-only.
   - Step 1's PASS in this run stands: it finished at 18:29:31, before the kill switch went on.
2. **Run 18:35, step 3 NOT APPROVED:**
   - The approval was pending at 18:41:55 (default 120 s window), but the owner could not see it in the dashboard, and it expired.
   - Likely cause, not verified: the browser page was still on the dashboard from before the stack restart and had to be reloaded.
3. **18:46:** a step-3 retry was stopped by the main session **before any fault was injected**, to add the 300 s override; its stack was stopped and its lock released. No result file exists for it.
4. **18:47:** a launch failed on argument parsing (a quoting error in the launcher). Nothing was started.

## Files (SHA256)

```
1736d666e93df7750e24e4745918922a3bd16f9ba58aea90dbafc0ddfd9a9e0a  docs/results/demo_rehearsal_20261024-1826.md
41cf0ddcf57a43e38ac9a7fd0da39fbb3d2a6616acc18d21624625fb4a42357a  results/live-checks/demo_rehearsal_20261024-1826.json
a46494b3aff28fda1db746bedc77bffec4bde25a97f0996e08b1c5fabe3f8da1  docs/results/demo_rehearsal_20261024-1835.md
07246bf53ee1552f02296fec3daec462ae6a58045f55584a479a0f4d375157de  results/live-checks/demo_rehearsal_20261024-1835.json
fcbc3ffe1de30d1214eb6f8bff1b4e6cb7cea1148a099bafae3864ede13590bb  docs/results/demo_rehearsal_20261024-1849.md
8f7f636366df9a9cca522b7e0edc4931c0df9b647ac888da087b2c1ca031bd0d  results/live-checks/demo_rehearsal_20261024-1849.json
6a259bf1434f0e261a091c4a735c12452dda5d33d20bd4c443e363483e62006c  scripts/demo_rehearsal_ds1.py
```

## For the demo plan
- **Autopilot demo faults: crash and disk fill.** Both passed with no action needing approval and nothing else executed.
- **Bad deploy on payments:** ask-first, approved by a person in the dashboard, with the 300 s window. Reload the dashboard after any stack restart.
- **Before the judges:** with the stack up, free RAM was 2.4-2.6 GB. Keep other apps closed.
