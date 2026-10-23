# Continue EternalAI (on this or another PC)

Updated 2026-10-23, 19:20 IST, 40 minutes before the code freeze (20:00 IST). Everything in git is on GitHub, branch
`plan-complete`. The last **live-verified** state is tag `demo-stable-1` (Phase 1, live check 17/17).

## 0. State at the freeze

| area | state |
|---|---|
| Phase 0 gap matrix | done: `docs/PLAN_GAP_CLOSURE.md` (section F = owner's answers, G = progress) |
| Phase 1 safety | done; **live** 17/17 (`docs/results/live_check_phase1.md`); tag `demo-stable-1` |
| Phase 3 prediction | code done; **live smoke only** (2 runs, excluded seeds): memory leak warned 37.1 s, gradual disk fill 86.1 s before the limit (`results/forecast-check/v3-smoke.md`). The 20 pre-registered runs were NOT run. |
| Phase 4a: forest-only anomaly -> approval | code done, **tests only** |
| Phase 4a: two close root candidates -> abstain | code done, **tests only**; margin 0.1215 chosen on 316 out-of-fold training incidents (`docs/results/root_margin.md`) |
| Phase 5 light: SQLite learn store + POST /feedback | code done, **tests only** |
| Phase 4 core (KB, outcome ranking, dataset-A classifier), Phase 7 re-runs, Kubernetes, Telegram | not started |

**For the demo:** `demo-stable-1` is the state that passed a live check. `plan-complete` HEAD adds the items above, which pass
the test suite but have not been checked on the live stack (except the two forecast smoke runs).

## 1. Not in git: copy by hand (USB / OneDrive), never commit

| item | old location | needed for |
|---|---|---|
| `.env` (approval token, API keys; must contain `CHAOS_TOKEN=<long random>`) | `D:\eAI\eAI-release\.env` | starting the stack |
| training runs, 105 runs, 8 MB (data hash `2f14ce10...`) | `D:\eAI\eAI-workspace\eAI\data\runs_all` | retraining; re-choosing the root margin |
| plan dataset (owner's files; read-only; never commit the xlsx) | `D:\eAI\plan_dataset\` | Phase 4 core |
| Claude Code memory (copies are in `docs/session/`) | `C:\Users\premy\.claude\projects\C--Users-premy\memory\` | session rules |

## 2. Set up a new PC (PowerShell)

```powershell
mkdir D:\eAI -Force; cd D:\eAI
git clone https://github.com/py007105/eAI eAI-release
cd D:\eAI\eAI-release
git switch plan-complete
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider        # expect about 490 passed, 2 deselected
```
Then by hand:
1. Copy `.env` to `D:\eAI\eAI-release\.env`. Check: `git check-ignore .env` prints `.env`.
2. Copy the training runs (e.g. to `D:\eAI\data\runs_all`).
3. Put the plan dataset at `D:\eAI\plan_dataset\`.
4. Create the lock file:
   `Copy-Item docs\DOCKER_SCHEDULE.md D:\eAI\STACK_LOCK.md; Add-Content D:\eAI\STACK_LOCK.md "FREE | last: none"`.
   The schedule in it ends at the freeze; write a new one for after it.
5. Start Docker Desktop and build once: `docker compose --profile releases build`.

Paths written into scripts (keep the same layout or adjust them):
- `D:\eAI\STACK_LOCK.md` in `scripts/stack_lock.py`;
- `C:\Program Files\Docker\Docker\resources\bin` in the live-check scripts;
- the Codex worktree `D:\eAI\eAI-codex`.

To run the demo from the verified state: `git switch --detach demo-stable-1`, then follow `docs/DEMO.md`. Before that,
add `CHAOS_TOKEN` to `.env`; the old launcher predates that rule.

## 3. Next steps, in order

1. **Forecast check v3:** `python scripts/live_check_phase3.py` (about 1 h 50 min).
   - Run it exactly as designed; no tuning on these seeds.
   - Report the lead times.
   - Report that the time-to-limit estimate runs late: the 120 s look-back includes flat data from before the fault.
   - Report that "limit" means 95% of the memory limit; no OOM kill was seen.
   - A shorter look-back is allowed only as a pre-registered v4 on new seeds.
2. **One Phase 4a live check** covering:
   - forest-only anomaly -> approval;
   - close root candidates -> abstain;
   - learn-store rows written after real incidents;
   - POST /feedback.

   Label each item "verified live" or "tests only". If it passes, tag `demo-stable-2` and push the tag.
3. **Phase 4 core:**
   - knowledge-base files into `data/kb/`, with source columns kept;
   - loader;
   - outcome-ranked fix choice wired into the engine;
   - dataset-A classifier, reported next to the current one on the same held-out data.
4. **Phase 7:** re-run the policy-affected scenarios (>= 5 seeds) and label every number with its policy file and system.
5. **Optional, with Codex:** Kubernetes package A (section 5).

Each report covers: commits, test count, the verified-live list, % per area, and Docker schedule status.

## 4. Prompt for Claude Code (in `D:\eAI\eAI-release`)

```
Continue the EternalAI project. Repository: D:\eAI\eAI-release, branch plan-complete (https://github.com/py007105/eAI).
Read fully first: docs/CONTINUE_ON_NEW_PC.md, docs/session/*.md (my working rules and the project state),
docs/PLAN_GAP_CLOSURE.md sections F and G, docs/DOCKER_SCHEDULE.md, docs/FORECAST_CHECK.md (v3 part).
The plan is docs/ETERNALAI_PLAN.md.

Rules:
- Never read or print .env or any token; live checks pass throwaway tokens through the environment, as the existing
  live-check scripts do.
- You may push plan-complete and every demo-stable-N tag (never force-push). Ask before anything else that leaves the machine.
- Never docker compose down -v or delete volumes. Use the Docker lock D:\eAI\STACK_LOCK.md (scripts/stack_lock.py).
- Small commits; full test suite after every commit; numbers only from scripts and results files; nothing tuned after seeing
  results; every item reported as "verified live" or "tests only". Times in IST.
- Python: D:\eAI\eAI-release\.venv. Training runs: <PATH OF runs_all>. Plan dataset: D:\eAI\plan_dataset\ (read-only; never
  commit the raw xlsx; copy only what Phase 4 needs into data/kb/ with source columns kept).

First: git status, git log --oneline -5, the test suite, docker info and D:\eAI\STACK_LOCK.md; report. Then write a new
Docker schedule (the old one ended at the 2026-10-23 freeze), and continue with docs/CONTINUE_ON_NEW_PC.md section 3 in
order. Start long runs detached so they survive if the session stops. Report after each step.
```

## 5. Codex (optional; Kubernetes package A)

Once, in a normal PowerShell:
```powershell
cd D:\eAI\eAI-release
git worktree add D:\eAI\eAI-codex -b friend/phase2-k8s plan-complete
Copy-Item D:\eAI\eAI-release\.env D:\eAI\eAI-codex\.env
cd D:\eAI\eAI-codex
codex          # an approval mode that asks before running commands; never "full access"
```
Prompt for Codex:
```
You are the second AI coding session on the EternalAI project; another session (Claude Code, the "main session") works on
this same Windows machine at the same time. Read everything below first.

WHERE: your folder (the only place you work) is D:\eAI\eAI-codex, a git worktree; your branch is friend/phase2-k8s.
The main session's folder D:\eAI\eAI-release (branch plan-complete): never read, edit or run git there. Both share one .git,
one Docker daemon (Compose project "eai"), ports, RAM and image names. Docker schedule + lock: D:\eAI\STACK_LOCK.md
(schedule at the top, LAST line = lock; Docker/kind only in "codex" windows). Contract: docs\HANDOFF_FRIEND.md (sections 1,
2, 3, 5, 6, 9-12) and AGENTS.md. Requirements: docs\PLAN_GAP_CLOSURE.md sections A, F, G (do not edit). Patterns:
scripts\live_check_phase1.py, scripts\stack_lock.py, tests\test_autopilot_path.py. Python: only D:\eAI\eAI-codex\.venv.

WORK: package A, Kubernetes minimal (handoff section 6): Driver interface (DockerDriver = current executor, unchanged),
KubernetesDriver (restart, scale, rollback, delete pod), Kubernetes metrics source, annotation service map with static
fallback, verification of root + callers, Helm chart + namespaced least-privilege RBAC, one scripted kind end-to-end check
with Online Boutique. Not: leader election, kube-prometheus-stack install, Telegram, knowledge base, prediction, learn store,
benchmarks.

RULES: commit only to friend/phase2-k8s; never push, force-push, rebase, reset --hard, amend, tag, delete branches,
git worktree remove/prune, git clean, git gc --prune; never check out plan-complete here; get new work with
`git merge plan-complete`. Never git add -A / git add . ; show git status, add by name. Small commits; shared files
(handoff section 5) only in separate "shared:" commits. Never read/print/log/commit .env, tokens, keys, kubeconfig; log
only type(e).__name__. Before any docker/kind command that changes something: codex window + last line FREE, then
stack_lock.take("codex", ...) and later stack_lock.release("codex", ...). Never kind together with Compose; kind image tag
eai/eternalai:k8s-dev; port-forwards 18000-18099; never down -v, never delete volumes, never system prune. Ask before
downloading kind/helm (pinned, SHA256 verified, binaries in D:\eAI\tools). No fakes outside tests\, no invented numbers,
every feature checked live by a committed script, report "verified live" or "tests only", never weaken a check. After
EVERY commit run .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider and show the last line.

FIRST STEPS, then STOP and wait for my OK:
1. Read AGENTS.md, docs\HANDOFF_FRIEND.md, docs\PLAN_GAP_CLOSURE.md sections A, F, G.
2. Show git branch --show-current, git status, git log --oneline -3, git log --oneline HEAD..plan-complete,
   git check-ignore .env (do not open .env).
3. git merge plan-complete if it has new commits.
4. py -3.14 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt; run the tests.
5. Show D:\eAI\STACK_LOCK.md (do not change it).
6. Summarise package A in about 10 lines and list the 10 commits of handoff prompt 11.4.
After my OK: one commit at a time; show the diff summary and test line after each, then wait for "next".
```
When Codex reports "package A ready on friend/phase2-k8s at <hash>", tell the main session; it merges, re-runs the tests
and live checks, and reports.
