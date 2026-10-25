# Coordination record (integration owner: Claude, main session)

Committed 2026-10-23 20:51 IST (`46a1aa4`); schedule updated after the first runs. This is the current, single coordination record. When it disagrees with an older
document (`docs/HANDOFF_FRIEND.md`, `docs/CONTINUE_ON_NEW_PC.md`, `docs/DOCKER_SCHEDULE.md`), this file wins.

## 1. Freeze
- **The implementation freeze is lifted for assigned development** (Prem, 2026-10-23 evening). Each owner works only in
  their own paths (section 2).
- **`demo-stable-1` stays the fallback demo build** (commit `49155ea`). It is never moved. Newer code becomes a demo
  candidate only when its documented acceptance gates pass and a new `demo-stable-N` tag is created.
- Push permissions are unchanged:
  - the main session pushes `plan-complete` and new `demo-stable-N` tags;
  - teammates push only their own branch, and only after Prem says "push";
  - nobody force-pushes or moves a tag.

## 2. Ownership and protected paths

| owner | branch | owns | notes |
|---|---|---|---|
| **Claude** (main session, `D:\eAI\eAI-release`) | `plan-complete` | integration; every shared file (section 3); prediction/forecast validation; Phase 4a (forest-only -> approval, close root candidates -> abstain); learning-store validation; Package C (knowledge base, outcome-ranked fixes, dataset-A classifier); final evaluation; connecting Mihir's components to `dashboard/app.py`; the deferred Docker socket proxy (roadmap only, no commitment) | merges teammate branches one at a time, only when handed back |
| **Codex** (`D:\eAI\eAI-codex`) | `friend/phase2-k8s` (to be created from `plan-complete`) | `engine/drivers/`, `engine/sources/`, `engine/verify_k8s.py`, `deploy/helm/`, `deploy/kind/`, `deploy/online-boutique/`, `tools/kind_e2e.py`, `docs/KUBERNETES.md` | **Kubernetes first.** Contract: `docs/HANDOFF_FRIEND.md` sections 1, 5, 6 |
| **Codex** (reserved) | `friend/phase6-telegram` at `925d8f2` | `engine/notify/`, `tests/test_notify_*.py`, `tests/test_telegram.py`, `docs/TELEGRAM_CONTINUE_ON_NEW_PC.md`, `docs/NOTIFICATIONS.md` | preserved, paused; not merged; not wired into the brain |
| **Rajat** | `team/rajat-zscore-nab` | `engine/zscore_detector.py` (new), `ml/data/download_nab.py`, `ml/models/eval_nab.py`, `tests/test_zscore_detector.py`, `tests/test_eval_nab.py`, `docs/NAB_EVAL.md`, `docs/results/nab_detector_eval.md`, `docs/handback/rajat.md` | offline public-data evaluation; no live claim |
| **Rajat** (next task, proposed 2026-10-24) | `team/rajat-smd-eval` from `a748eb1` (merges after `team/rajat-zscore-nab`, PR #2); push not yet authorised | `docs/SMD_EVAL.md`, `ml/data/download_smd.py`, `ml/models/eval_smd.py`, `tests/test_eval_smd.py`, `docs/results/smd_detector_eval.md`, `docs/handback/rajat-smd.md` | SMD half of gap row D6; offline public data; task file on Prem's Desktop `RAJAT_NEXT_TASK.md` |
| **Mihir** | `team/mihir-dashboard-charts` | `dashboard/charts.py`, `dashboard/explain_words.py`, `dashboard/charts_labels.py`, `dashboard/preview/`, `tests/test_dashboard_charts.py`, `tests/test_dashboard_explain.py`, `docs/DASHBOARD_CHARTS.md`, `docs/screenshots/charts_*.png`, `docs/handback/mihir.md` | synthetic data only; Claude integrates |
| **Sanskar** | `team/sanskar-docs-runbooks-qa` | `docs/team-qa/` | documentation and manual QA only |

The teammates' full guides are on Prem's Desktop (`RAJAT_TASKS.md`, `MIHIR_TASKS.md`, `SANSKAR_TASKS.md`); their
ownership table is the same as above.

## 3. Shared files and edit windows
Shared files are edited only by Claude, unless a window is listed here:
- `engine/engine.py`, `api.py`, `policy.py`, `rulebook.py`, `rulebooks/`, `config.py`, `detect.py`, `forecast.py`,
  `store.py`, `executor.py`, `collector.py`, `baselines.py`;
- `docker-compose*.yml`, `dashboard/app.py`, `views.py`, `labels.py`, `theme.py`;
- `requirements*.txt`, `pytest.ini`, `.gitignore`, `README.md`, `AGENTS.md`, `docs/PLAN_GAP_CLOSURE.md`;
- the existing tests.

| window | who | what exactly | how |
|---|---|---|---|
| open | Codex | the `shared:` lines listed in `docs/HANDOFF_FRIEND.md` section 5 for package A: `make_driver()` construction in `engine.py` (one line), `config.load_topology()` appended to `config.py`, verifier choice by `RUNTIME` (one line), pinned `kubernetes` line in `engine/requirements.txt` | separate `shared:` commits on `friend/phase2-k8s`; reviewed and merged by Claude |
| none | Rajat, Mihir, Sanskar | no shared-file edits | integration requests in their hand-back notes |

## 4. Integration contracts (interfaces Claude will wire)
- **Rajat**: `engine/zscore_detector.py` with `ZScoreDetector(...).update(key, value, t=None) -> ZResult(z, hot,
  anomalous, mean, std, n_baseline)` and `explain(key)`. It must reproduce `engine/baselines.ZScoreDetector` with the
  same constants. Claude decides how a z-score result combines with `detect.service_anomalous`. Until then the engine is
  unchanged.
- **Mihir**:
  - `dashboard/charts.History.add({"t", "services"})`;
  - `service_figure(history, service, lang)`;
  - `incident_stats(incidents)`;
  - `stats_table(stats, lang)`;
  - `dashboard/explain_words.explain_service(name, features, lang)`.

  Claude feeds `History` from the dashboard `Poller`'s `/services` result each second, adds the cards to `dashboard/app.py`,
  and verifies them live. The input shapes are those of the brain's `GET /services` and `GET /incidents`.
- **Codex (package A)**:
  - the `Driver` protocol of `docs/HANDOFF_FRIEND.md` section 6.3;
  - `DockerDriver` must leave the Docker path's behaviour and audit records unchanged (`tests/test_autopilot_path.py`
    must pass unchanged).
- **Sanskar**: documents only; corrections to other documents arrive as integration requests in
  `docs/team-qa/HANDBACK.md`.

Hand-back: teammates send a PR to `plan-complete` (after Prem's "push") or a git bundle/zip to Prem. Codex reports
"package A ready on friend/phase2-k8s at <hash>". Claude merges one branch at a time (`--no-ff`), runs the full suite and
the relevant live checks on the combined result, and records it in `docs/PLAN_GAP_CLOSURE.md` section G.

## 5. Docker: schedule and lock
- **Lock procedure** (atomic since 2026-10-24): ownership is the owner file `D:\eAI\STACK_LOCK.owner`, created only
  through `tools/stack_lock.py`:
  - `take(who, what, images)` creates the file with O_EXCL, so of two sessions exactly one wins, and writes the display line;
  - `release(who, images)` frees it only with the caller's own token.

  Rules:
  - The last line of `D:\eAI\STACK_LOCK.md` is only a display. **Seeing FREE is not ownership**, and nobody edits that
    line by hand.
  - Codex takes the lock the same way:
    `python -c "import sys; sys.path.insert(0,'scripts'); import stack_lock; print(stack_lock.take('codex','kind window','friend/phase2-k8s@<hash>'))"`,
    and releases it with that token.
  - A scheduled window never overrides an active owner.
  - A crashed owner's file is never removed automatically; check the `pid` in it first.
  - Before taking the lock, also check the real state (`docker ps`, `kind get clusters`, running `python`/`kind`
    processes). Never delete volumes.
- **RAM:** the machine has 15.7 GB in total; often only 2-3 GB are free. Each window needs about 3 GB free (Compose) or
  about 6 GB (kind + Online Boutique). If that is not free, the run waits.
- **Attribution:** every run records the commit, the rulebook file and the image build (`images built from
  <branch>@<hash>` on the lock line, and the commit in the results file).

| when (IST) | who | what |
|---|---|---|
| Fri 23, 20:53-21:00 (done) | main | Phase 4a live check (`tools/live_check_phase4a.py`): 10/10 |
| Fri 23, 21:02 - about 23:00 (running) | main (detached) | forecast check v3, the 20 pre-registered runs (`tools/live_check_phase3.py`) |
| Fri 23, after the forecast check releases the lock, until the sequence releases it | main (detached; pinned checkout `D:\eAI\eAI-eval-<commit>`) | `tools/run_v3_sequence.py` holds the lock for the whole run: build; Phase 1 + Phase 4a live checks; evaluation v3 (50 runs, `docs/EVALUATION_V3_PLAN.md`); controlled checks G4-G6 (`docs/RELEASE_GATE.md`). No finish time is promised. **If it still holds the lock at 07:00 Sat, Codex's window 1 starts only when the lock line reads FREE**; the main session then moves Codex's window in this table |
| Sat 24, 07:00-12:00 | codex | kind window 1 |
| Sat 24, 12:00-14:00 | main | Package C live check / regression (if Package C is ready) |
| Sat 24, 14:00-19:00 | codex | kind window 2 |
| Sat 24, 21:00 - Sun 25, 05:00 | main (detached) | reserve: re-runs of failed v3 runs, or a pre-registered forecast v4 |
| Sun 25, 07:00-12:00 | codex | kind window 3 (end-to-end on merged code) |
| Sun 25, 13:00-17:00 | main | final regression; demo-candidate gates |

Teammates never use this machine's Docker without a slot from Prem. On their own laptops they use their own Docker.

## 6. Reading this handoff from the Codex worktree
Both worktrees share one `.git`, so Codex sees `plan-complete` immediately, with no fetch:
```powershell
git -C D:\eAI\eAI-codex show plan-complete:docs/COORDINATION.md
git -C D:\eAI\eAI-codex log --oneline -5 plan-complete
```
To bring the main session's work into a `friend/...` branch: `git merge plan-complete` (merge, never rebase).

## 7. Standing limits (do not lose these)
- **Seed 426 (cpu_burn):** on an unseen fault, autopilot once restarted a healthy service; neither the novelty gate nor
  the ranker caught it (`docs/postmortems/cpu_burn_seed426.md`). The close-candidates margin (0.1215) would **not** have
  caught it (support gap 0.161). No check that passes on scripted faults establishes general safety on unseen faults.
- Telegram is not connected to the brain. Kubernetes is not started. The Docker socket proxy is deferred.

## 8. Overnight sequence: executions (append-only)
| when (IST) | checkout | commit | execution | state |
|---|---|---|---|---|
| 23 Oct 21:11 | `D:\eAI\eAI-eval-3208bf0` | `3208bf0` | (no ID) | stopped at 21:22 while still waiting for the lock: it did not hold the lock across steps. Ran nothing |
| 23 Oct 21:26 | `D:\eAI\eAI-eval-7961c1c` | `7961c1c` | (no ID) | stopped at 22:19 while still waiting for the lock: controlled-check claims and stale-result protection were insufficient. Ran nothing |
| 23 Oct 22:25 | `D:\eAI\eAI-eval-67211f8` | `67211f8` (image build inputs identical to `7961c1c`) | `20261023T222518-d60e18cd` | stopped at 22:27 while still waiting: lock acquisition was not atomic and there was no execution manifest. Ran nothing |
| 24 Oct 00:18 | `D:\eAI\eAI-eval-71eb2f5` | `71eb2f5` (image build inputs identical to `7961c1c`) | `20261024T001813-4cedc8bf` | lock taken atomically at 00:18; running; manifest `results/executions/<ID>/manifest.json` |
| 24 Oct 04:26 | `D:\eAI\eAI-eval-71eb2f5` | `71eb2f5` | `20261024T001813-4cedc8bf` | finished; **lock released 04:26** (`sequence.log`; actual handoff time). Phase 1 17/17, Phase 4a 10/10; evaluation INCOMPLETE 26/50 (memory-guard timeouts 02:58 and 03:58); controlled 6/7, G5 INCOMPLETE. No promotion. Record: `docs/results/v3_execution_20261024T001813-4cedc8bf.md` |
| 24 Oct 12:37-12:40, 12:53-12:57 | `D:\eAI\eAI-eval-71eb2f5` (stack) + integration worktree (dashboard source) | candidate images `71eb2f5`; dashboard `e1e8d3e` | (not a gate execution) | real-dashboard live check, main's own lock in main's 12:00-14:00 slot: first attempt failed before any check (page-load limit), second 5/5 (`docs/results/dashboard_charts_live.md`). Lock released 12:57:48 |

### Memory observed on 24 Oct (read-only; the overnight cause was not recorded and is not assumed)
| time (IST) | free RAM | containers | largest consumers (working set) |
|---|---|---|---|
| 08:11 | 1.07 of 15.69 GB | none | OneDrive 2.5 GB, Brave 2.0 GB, ChatGPT 1.3 GB, vmmemWSL 0.9 GB, Codex 0.5 GB |
| 12:14 | 1.92 GB | none | Brave 4.1 GB, ChatGPT 1.4 GB, vmmemWSL 0.9 GB, Codex 0.5 GB |
| 12:36 | 3.30 GB | none | Brave 2.8 GB, ChatGPT 1.1 GB, VS Code 1.0 GB, vmmemWSL 0.9 GB |

The live checks and the evaluation keep their memory guards (1.5 GB for evaluation runs). No application was closed and no
Docker/WSL limit was changed by the main session.

### Main session's next Docker work (needs about 3 GB free; Codex's windows are not used)
- `tools/run_gate_sequence.py --reference 20261024T001813-4cedc8bf`: G2-G7 again in one execution, with the new G5
  stimulus (`tools/live_check_g5.py`). Estimate from measured durations: 62-75 min.
- `tools/resume_eval_v3.py --original 20261024T001813-4cedc8bf`: exactly the 24 missing evaluation cases. Estimate:
  85-100 min at 3.3-4 min per run, longer if the memory guard waits.
- Planned for main's slot Sat 24, 21:00 - Sun 25, 05:00, from the pinned checkout `D:\eAI\eAI-eval-71eb2f5`.

### Overnight runner launched 24 Oct 13:25:37 IST (main session)
- One detached runner: `tools/run_overnight.py` from `D:\eAI\eAI-combined-519a5f6`, **PID 16564** (launcher 29288), log
  folder `D:\eAI\overnight-20261024` (`runner.log`, `status.json`, one `*.out.log` per step). Before 21:00 it only sleeps:
  no Docker, no lock.
- Window: 21:00 Sat - 05:00 Sun IST (main's slot). It takes the lock only when it reads FREE and >= 3 GB RAM is free; it
  holds it across: gate (`D:\eAI\eAI-eval-71eb2f5`, G2-G7 in one execution, latest start 23:30), evaluation resume (24
  missing cases, latest start 01:30), combined deployment (`519a5f6` images, latest start 04:15). Expected without memory
  waits: gate 62-75 min, resume 85-100 min, combined about 20-25 min, so about 21:00-00:30.
- It never pushes, tags or promotes. Codex's window 3 (Sun 07:00) is not touched.
