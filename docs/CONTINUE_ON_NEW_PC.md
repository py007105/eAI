# Continue on another PC (written 2026-10-21 ~09:30 IST)

Everything in git is on GitHub, branch `plan-complete` (tags `demo-stable-1` and earlier). Start with:
```
git clone https://github.com/py007105/eAI && cd eAI && git switch plan-complete
py -3.14 -m venv .venv && .venv\Scripts\python -m pip install -r requirements-dev.txt && .venv\Scripts\python -m pytest -q -p no:cacheprovider
```

## Not in git: copy these by hand (USB / OneDrive), never commit them
| item | old location | why it matters |
|---|---|---|
| `.env` (tokens, API keys; add `CHAOS_TOKEN`) | `D:\eAI\eAI-release\.env` | the stack refuses to start without CHAOS_TOKEN |
| training runs (105 runs, 8 MB) | `D:\eAI\eAI-workspace\eAI\data\runs_all` | needed for the root-margin computation and any retraining (data hash 2f14ce10...) |
| plan dataset (owner's files) | `D:\eAI\plan_dataset\` (not yet present on the old PC) | Phase 4 KB + dataset-A classifier |
| Claude memory files | `C:\Users\<user>\.claude\projects\C--Users-premy\memory\` | session rules (push/tag only with a go, IST times, Codex lock) |
| Docker schedule + lock | `D:\eAI\STACK_LOCK.md` | copy of `docs/DOCKER_SCHEDULE.md`; recreate with a last line `FREE | last: none` |

Hard-coded paths to adjust on a new PC: `D:\eAI\STACK_LOCK.md` (`scripts/stack_lock.py`), the Docker path
`C:\Program Files\Docker\Docker\resources\bin` (live-check scripts), the Codex worktree `D:\eAI\eAI-codex`.

## Where the work stands
- Phase 0 and Phase 1 done; Phase 1 live check 17/17 (`docs/results/live_check_phase1.md`); tag `demo-stable-1`.
- Phase 3 F1/F3: forecast now runs every tick (`d084b20`); evaluator opt-ins `observe_full` and `variant: gradual`
  (`f737a17`); forecast check v3 pre-registered (`docs/FORECAST_CHECK.md`). Smoke runs (excluded seeds 3900/3901,
  `results/forecast-check/v3-smoke*`): memory leak warned 37.1 s before 95% of the memory limit, gradual disk fill 86.1 s
  before the threshold. **Next: run the 20 pre-registered runs** with `python scripts/live_check_phase3.py`, exactly as
  designed; report the late time-to-limit estimate and that "limit" = 95% of the memory limit (no OOM kill was seen).
- Phase 4a code done, not yet live-checked: forest-only anomaly -> approval (`18a4b38`), two close root candidates ->
  abstain (`d1c710d`, margin file `models/artifacts/root_margin.json` NOT yet created: run
  `models/train_models.py --runs <runs_all> --no-save --out <tmp.md> --oof-rank-out <oof.json>` (~15 min), then
  `models/choose_root_margin.py --oof <oof.json>`), SQLite learn store + POST /feedback (`84a3094`).
  Then ONE live check of these four items and tag `demo-stable-2` (push the tag).
- Then: Phase 4 core (KB loader, outcome-ranked fixes, dataset-A classifier next to the current one), Phase 7 re-runs
  (schedule: `docs/DOCKER_SCHEDULE.md`).
- Codex (if used): package A Kubernetes first, `docs/HANDOFF_FRIEND.md`, `AGENTS.md`.
- Owner's answers and scope: `docs/PLAN_GAP_CLOSURE.md` sections F and G. Plan copy: `docs/ETERNALAI_PLAN.md`
  (numbers in its §4/§19/§20 are from the old prototype and still to be replaced by measured ones).
