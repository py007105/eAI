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
| **Codex** (`D:\eAI\eAI-codex`) | `friend/phase2-k8s` (to be created from `plan-complete`) | `eternalai/drivers/`, `eternalai/sources/`, `eternalai/verify_k8s.py`, `deploy/helm/`, `deploy/kind/`, `deploy/online-boutique/`, `scripts/kind_e2e.py`, `docs/KUBERNETES.md` | **Kubernetes first.** Contract: `docs/HANDOFF_FRIEND.md` sections 1, 5, 6 |
| **Codex** (reserved) | `friend/phase6-telegram` at `925d8f2` | `eternalai/notify/`, `tests/test_notify_*.py`, `tests/test_telegram.py`, `docs/TELEGRAM_CONTINUE_ON_NEW_PC.md`, `docs/NOTIFICATIONS.md` | preserved, paused; not merged; not wired into the brain |
| **Rajat** | `team/rajat-zscore-nab` | `eternalai/zscore_detector.py` (new), `data/download_nab.py`, `models/eval_nab.py`, `tests/test_zscore_detector.py`, `tests/test_eval_nab.py`, `docs/NAB_EVAL.md`, `docs/results/nab_detector_eval.md`, `docs/handback/rajat.md` | offline public-data evaluation; no live claim |
| **Mihir** | `team/mihir-dashboard-charts` | `dashboard/charts.py`, `dashboard/explain_words.py`, `dashboard/charts_labels.py`, `dashboard/preview/`, `tests/test_dashboard_charts.py`, `tests/test_dashboard_explain.py`, `docs/DASHBOARD_CHARTS.md`, `docs/screenshots/charts_*.png`, `docs/handback/mihir.md` | synthetic data only; Claude integrates |
| **Sanskar** | `team/sanskar-docs-runbooks-qa` | `docs/team-qa/` | documentation and manual QA only |

The teammates' full guides are on Prem's Desktop (`RAJAT_TASKS.md`, `MIHIR_TASKS.md`, `SANSKAR_TASKS.md`); their
ownership table is the same as above.

## 3. Shared files and edit windows
Shared files are edited only by Claude, unless a window is listed here:
- `eternalai/engine.py`, `api.py`, `policy.py`, `rulebook.py`, `rulebooks/`, `config.py`, `detect.py`, `forecast.py`,
  `store.py`, `executor.py`, `collector.py`, `baselines.py`;
- `docker-compose*.yml`, `dashboard/app.py`, `views.py`, `labels.py`, `theme.py`;
- `requirements*.txt`, `pytest.ini`, `.gitignore`, `README.md`, `AGENTS.md`, `docs/PLAN_GAP_CLOSURE.md`;
- the existing tests.

| window | who | what exactly | how |
|---|---|---|---|
| open | Codex | the `shared:` lines listed in `docs/HANDOFF_FRIEND.md` section 5 for package A: `make_driver()` construction in `engine.py` (one line), `config.load_topology()` appended to `config.py`, verifier choice by `RUNTIME` (one line), pinned `kubernetes` line in `eternalai/requirements.txt` | separate `shared:` commits on `friend/phase2-k8s`; reviewed and merged by Claude |
| none | Rajat, Mihir, Sanskar | no shared-file edits | integration requests in their hand-back notes |

## 4. Integration contracts (interfaces Claude will wire)
- **Rajat**: `eternalai/zscore_detector.py` with `ZScoreDetector(...).update(key, value, t=None) -> ZResult(z, hot,
  anomalous, mean, std, n_baseline)` and `explain(key)`. It must reproduce `eternalai/baselines.ZScoreDetector` with the
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
- **Lock procedure** (unchanged): `D:\eAI\STACK_LOCK.md`.
  - The top of the file is the schedule (copied from section 5 here); its **last line** is the lock.
  - Use `scripts/stack_lock.py` (`take(who, what, images)` / `release(who, images)`); it changes only the last line.
  - Before taking the lock, check the real state: `docker ps`, `kind get clusters`, and running `python`/`kind`
    processes. A FREE line does not prove the engine is idle.
  - Never overwrite a HELD line held by someone else. Never delete volumes.
- **RAM:** the machine has 15.7 GB in total; often only 2-3 GB are free. Each window needs about 3 GB free (Compose) or
  about 6 GB (kind + Online Boutique). If that is not free, the run waits.
- **Attribution:** every run records the commit, the rulebook file and the image build (`images built from
  <branch>@<hash>` on the lock line, and the commit in the results file).

| when (IST) | who | what |
|---|---|---|
| Fri 23, 20:53-21:00 (done) | main | Phase 4a live check (`scripts/live_check_phase4a.py`): 10/10 |
| Fri 23, 21:02 - about 23:00 (running) | main (detached) | forecast check v3, the 20 pre-registered runs (`scripts/live_check_phase3.py`) |
| Fri 23, after the forecast check releases the lock, until the sequence releases it | main (detached; pinned checkout `D:\eAI\eAI-eval-<commit>`) | `scripts/run_v3_sequence.py` holds the lock for the whole run: build; Phase 1 + Phase 4a live checks; evaluation v3 (50 runs, `docs/EVALUATION_V3_PLAN.md`); controlled checks G4-G6 (`docs/RELEASE_GATE.md`). No finish time is promised. **If it still holds the lock at 07:00 Sat, Codex's window 1 starts only when the lock line reads FREE**; the main session then moves Codex's window in this table |
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
