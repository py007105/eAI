# Hand-back: Z-score detector module + offline evaluation on public NAB data
- Assignment file: RAJAT_TASKS.md          - Branch: team/rajat-zscore-nab
- Starting commit: 65dd9fe014e2bdfe6cede2cd9f69b0a014604f93     - Final commit: the commit that adds this file (a file
  cannot contain its own hash; `git log -1 team/rajat-zscore-nab`). Earlier commits: `ff370f3`, `36172c5`, `c96e0e9`,
  `a0669fc`, `6a4d82b`.
- Merged plan-complete at checkpoints: none (`origin/plan-complete` was still at the baseline `65dd9fe` when work began)
- Environment: Windows 11, Python 3.13.5 (the only Python on this machine; assignment allows 3.12+), own clone at
  `D:\Eternal Ai\eAI-rajat`. Prem lifted the freeze for this assignment before Milestone 1.

## Changed files
- `eternalai/zscore_detector.py`: new standalone per-signal z-score detector (stdlib + numpy only).
- `tests/test_zscore_detector.py`: 32 tests (equivalence with the benchmark port, warm-up, no absorption, streak,
  min_gap, directions, missing values, per-key state, determinism).
- `docs/NAB_EVAL.md`: pre-registration v1, committed before the NAB download and before any evaluation output.
- `data/download_nab.py`: NAB downloader pinned to one commit; writes `data/raw/nab/MANIFEST.json`.
- `models/eval_nab.py`: the pre-registered evaluation; writes the results file.
- `tests/test_eval_nab.py`: 12 tests on synthetic series written inside the test.
- `docs/results/nab_detector_eval.md`: script output of the real run.
- `docs/handback/rajat.md`: this note.

Nothing else changed (`git diff --stat 65dd9fe...HEAD` lists only these eight paths). `eternalai/baselines.py` is
imported read-only by the tests and not edited.

## Requirements
| milestone / requirement | status | evidence |
|---|---|---|
| 0 set-up and baseline | done | branch at `65dd9fe`; baseline suite `489 passed, 2 deselected, 1 warning in 59.81s` (Python 3.13.5); nothing committed |
| 1 module + tests (a)–(h) | done | `ff370f3`; (a) `test_equals_baseline_port`: 4 seeded series × 4 metrics, every z/hot/anomalous/mean equal to `eternalai.baselines.ZScoreDetector` and alarms exercised; (b) `test_warmup_never_anomalous`; (c) `test_sustained_fault_not_absorbed`; (d) `test_three_in_a_row`; (e) `test_min_gap_blocks_tiny_gap`; (f) `test_directions`, `test_lower_streak_and_explain`; (g) `test_missing_values_change_nothing`; (h) `test_deterministic` |
| 2 pre-registration | done | `36172c5`, committed when `data/raw/` did not exist and before any output |
| 3 downloader | done | `c96e0e9`; refuses without a 40-hex commit (exit 2 for no `--commit` and for `--commit master`); downloaded 18 files at `ea702d7`, sizes equal GitHub's listing; `git check-ignore` shows `data/raw/` ignored by `.gitignore:15`; nothing under `data/raw/` staged |
| 4 evaluation + tests | done | script and tests `a0669fc` (committed before the real run); results `6a4d82b`; rerunning gives the same file apart from the "commit of the script" line |
| 5 hand-back | done | this file |

## Results (offline evaluation on public data; not live verified)
From `docs/results/nab_detector_eval.md`, all 17 series pooled, 30 evaluable windows (0 excluded):

| detector | detected / evaluable | recall | precision (events) | false alarms per day | delay, min: median (range) |
|---|---|---|---|---|---|
| Z-up (primary z-score) | 11 / 30 | 0.367 | 0.174 | 1.146 | 265 (30–1095) |
| Z-two (secondary) | 15 / 30 | 0.500 | 0.161 | 2.016 | 265 (5–1095) |
| FT (primary fixed threshold) | 10 / 30 | 0.333 | 0.129 | 2.353 | 360 (20–1180) |
| FT-3 (secondary) | 3 / 30 | 0.100 | 0.113 | 0.663 | 1015 (5–1035) |

Reading: on this data the plan's z-score rule detects slightly more windows than the fixed threshold with about half
the false alarms per day, but both detectors find a minority of windows and most of their alarm events are false. The
counts are small (30 windows), so the difference between Z-up and FT is one window. On the 10 CPU series `FT`
(CPU > 90%) caught 4/16 and `Z-up` 5/16. Per-series numbers are in the results file; two series
(`ec2_cpu_utilization_77c1ca`, `ec2_cpu_utilization_fe7f93`) and `ec2_network_in_5abac7` produce most of Z-up's false
alarms. No parameter was changed after the run.

Plan comparison: the plan says "20 series, 327 events"; evaluated here are **17 series, 30 labelled windows**. The
plan's figure is not reproduced (it also counts SMD, which is roadmap).

## Tests
- Focused: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_zscore_detector.py tests/test_eval_nab.py` -> `44 passed in 4.61s`
- Full suite: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` -> `533 passed, 2 deselected, 1 warning in 82.09s (0:01:22)` (489 baseline + 32 + 12 new; the warning is the same Starlette deprecation as at the baseline)

## Live evidence
- Not live verified. This package is an offline evaluation on public data (NAB); EternalAI's live loop was not run,
  and the module is not wired into the engine.

## Dependencies and configuration changes
- None. The local `.venv` has only `requirements-dev.txt`. No manifest, `.gitignore` or config file was edited.
- One-time network access to `raw.githubusercontent.com` and `api.github.com` (to read the NAB commit and file list).

## Known limitations
- NAB `realAWSCloudwatch` only (17 univariate series, 30 windows); SMD is not evaluated (roadmap).
- Univariate: the live detector sees several signals per service at once; this says nothing about combinations.
- Not a live check; numbers do not transfer to the demo stack's 2-second loop. The z-score constants (warm-up 15,
  window 120, streak 3) were made for 2-second ticks; NAB is sampled every 5 minutes, so they span hours here.
- NAB windows are wide and start before the labelled anomaly point; delay is from the window start, not from onset.
- `Z-up`, `FT` and `FT-3` only alarm upwards.
- Licence: the assignment calls NAB AGPL-3.0; at the pinned commit `LICENSE.txt` is MIT (commit "chore: MIT License
  (#408)"). The data is not committed either way.
- Behaviour copied from the port on purpose (so (a) holds exactly): for a missing value `ZResult.z` is `0.0` and
  `anomalous` is `False` even if a streak was running; the streak itself is kept, so the next real value continues it.

## Shared-file integration requests (for Claude)
| file | interface needed | proposed change | why |
|---|---|---|---|
| `eternalai/engine.py` | `ZScoreDetector.update(key, value, t)`, `explain(key)` from `eternalai/zscore_detector.py` | Create one `ZScoreDetector` per engine with `SignalConfig`s built from `baselines.ZSCORE_METRICS` (p95, err, cpu, mem; direction `upper`). Each tick, in the per-service loop after `window_features`, call `update((s, m), latest_value_of_m, t=now)` for the four signals; skip the update while `down` or in the release grace period (so restarts are not learned and do not alarm). | Plan §9.1 wants two detectors side by side (gap row D1). |
| `eternalai/detect.py` | `service_anomalous(detector, feats, down, z_hot=False)` and `anomaly_source(...)` | Combine as `down or detector.anomalous(feats) or z_anomalous`, where `z_anomalous = any(r.anomalous for the service's 4 keys)`. Because the engine's `Persistence(k=3)` already needs 3 anomalous ticks, either feed `r.hot` (not `r.anomalous`) into `service_anomalous` or build the detector with `streak_needed=1`, so a fault is not delayed by 3 + 3 ticks. In `anomaly_source`, report `"zscore"` (one named signal) before `"forest_only"`, so "unusual combination" stays forest-only. | Keeps the one decision point; z-score evidence names a single signal, which the plain-words layer needs. |
| `dashboard/` (plain-words layer) | `explain(key)` dict: value, mean, z, direction, side | Turn it into "payments memory 246 MB, far above its normal 120 MB"; never show `z` itself. | Plan §9.1 "turning the score into words"; rule 8. |
| `eternalai/config.py` | env overrides | Optional `EAI_ZSCORE_ENABLED` (default off until a live check passes), and the four constants. | Plan §22 rule 6. |

Live verification needed after wiring (Claude): a committed script that injects latency/error/CPU/memory faults on the
real stack and records detection with and without the z-score path; until then "implemented only" for the engine path.

## Submission
- PR: none; no push was authorised. Bundle for Prem:
  `git bundle create "$HOME\Desktop\team-rajat-zscore-nab.bundle" 65dd9fe014e2bdfe6cede2cd9f69b0a014604f93..team/rajat-zscore-nab`
  (not yet sent; Rajat to send via the channel Prem chooses).

## Suggested integration order and rollback
- Integration: independent of the other teammates' branches (all paths are new files owned by Rajat); merge any time
  after Claude's checkpoint. The engine wiring above is a separate, later change by Claude.
- Rollback: Claude merges with `git merge --no-ff`; if needed, `git revert -m 1 <merge commit>` undoes it without
  rewriting history.
