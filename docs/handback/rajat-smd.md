# Hand-back: SMD detector evaluation (the second half of the plan's detector tests)
- Assignment file: RAJAT_NEXT_TASK.md (rules from RAJAT_TASKS.md)          - Branch: team/rajat-smd-eval
- Starting commit: 121024fa007ae5b0fc9dc8e0638c1e2b1cf6373a     - Final commit: the commit that adds this file (a file
  cannot contain its own hash; `git log -1 team/rajat-smd-eval`). Earlier commits: `0888d7d`, `eceed89`, `79084cd`,
  `b0f139c`.
- Merged plan-complete / PR #1 at checkpoints: none.
- Note on the start: when this task began, `origin/team/rajat-zscore-nab` was at `a748eb1`, not `121024f`. `a748eb1`
  is one commit on top of `121024f` that only updates the "Submission" section of `docs/handback/rajat.md` (3 lines),
  made when Prem authorised the PR #1 push (the PR is https://github.com/py007105/eAI/pull/2, which the task file calls
  "PR #1"). This branch starts at the commit the task file names, `121024f`, and does not touch that file; merging
  `team/rajat-zscore-nab` later brings it in without conflict.
- Environment: Windows 11, Python 3.13.5, own clone `D:\Eternal Ai\eAI-rajat`. No Docker.

## Changed files
- `docs/SMD_EVAL.md`: pre-registration v1, committed before any SMD file was downloaded.
- `data/download_smd.py`: downloader pinned to one 40-hex commit; prints the total size first; resumable (keeps files
  whose git blob hash matches); checks every file against the commit's git blob hash; writes `MANIFEST.json`.
- `models/eval_smd.py`: the pre-registered evaluation, one machine at a time; imports `eternalai.zscore_detector` and
  the scoring helpers of `models/eval_nab.py` (nothing copied or edited).
- `tests/test_eval_smd.py`: 14 tests on synthetic data written inside the tests.
- `docs/results/smd_detector_eval.md`: script output of the real run.
- `docs/handback/rajat-smd.md`: this note.

`git diff --stat 121024f...HEAD` lists only these six paths. No PR #1 file, shared file, manifest or `.gitignore` was
edited.

## Requirements
| milestone / requirement | status | evidence |
|---|---|---|
| 0 setup | done | branch at `121024f`; baseline `533 passed, 2 deselected, 1 warning in 55.22s`; nothing committed |
| 1 pre-registration | done | `0888d7d`, committed when `data/raw/smd/` did not exist; only GitHub metadata (commits, licence, file list with sizes) was read before it |
| 2 downloader | done | `eceed89` (committed before downloading); refuses without a 40-hex commit (exit 2 for no `--commit` and for `--commit master`); downloaded 113 files (28 machines × 4 folders + `LICENSE`), 485,982,236 bytes, 0 failed; every file matches the commit's git blob hash; `git check-ignore` shows `data/raw/` ignored by `.gitignore:15`; nothing under `data/raw/` staged |
| 3 evaluation + tests | done | script and tests `79084cd` (committed before the real run); results `b0f139c`; event count 327 = plan's 327; no setting changed after the run (no version 2) |
| 4 full suite + hand-back | done | see Tests; this file |

## Data
- OmniAnomaly `ServerMachineDataset`, commit `7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4` (2021-02-12).
- Licence: MIT (repository `LICENSE` and `ServerMachineDataset/LICENSE`, both MIT).
- Total download: 485,982,236 bytes (about 486 MB); local only, under `data/raw/smd/`, not committed.
- 28 machines, 38 metrics each; 708,405 train rows and 708,420 test rows in total; no missing values.

## Results (offline evaluation on public data; not live verified)
**Event count:** 327 anomaly events (maximal runs of 1s in `test_label`), equal to the plan's 327.

From `docs/results/smd_detector_eval.md`, 28 machines pooled:

| detector | detected / events | recall | alarm-event precision | false alarms per day | delay, min: median (range) |
|---|---|---|---|---|---|
| Z (primary: z-score, ≥ 1 of 38 metrics) | 173 / 327 | 0.529 | 0.094 | 11.525 | 3 (0–174) |
| Z-k2 (secondary: ≥ 2 metrics) | 174 / 327 | 0.532 | 0.146 | 6.469 | 4 (0–248) |
| FT (primary fixed threshold: train max + 10%) | 138 / 327 | 0.422 | 0.194 | 6.897 | 4 (0–839) |
| FT-3 (secondary: 3 rows in a row) | 81 / 327 | 0.248 | 0.166 | 1.622 | 8 (0–375) |

**Explanation score** (pre-registered): share of detected events where an alarming metric at the first alarm is in the
event's `interpretation_label` list: Z 134/172 = 0.779, Z-k2 150/173 = 0.867, FT 120/137 = 0.876, FT-3 69/81 = 0.852.
All 327 interpretation lines overlap a labelled event (index-convention check).

Reading:
- The plan's z-score rule finds about half of the SMD events, more than the train-max threshold (0.53 vs 0.42), and
  usually within a few minutes.
- But it raises many false alarms: about 11.5 per machine-day with "any 1 of 38 metrics", and only about 1 alarm
  event in 10 is true. Requiring 2 metrics (`Z-k2`) keeps the same recall and roughly halves the false alarms
  (6.5 per day), which is on a par with `FT`.
- False alarms are concentrated: three machines (`machine-3-1`, `machine-1-2`, `machine-3-9`) give 2,382 of `Z`'s
  5,434 false alarm events.
- When the rules do catch an event, the alarming metric is usually one of the labelled root-cause metrics (0.78–0.88).
  This supports naming the signal in plain words (plan §9.1).
- No parameter was changed after the run.

## Tests
- Focused: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_eval_smd.py` -> `14 passed in 0.99s`
- Full suite: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` -> `547 passed, 2 deselected, 1 warning in 67.27s (0:01:07)` (533 baseline + 14 new; the warning is the same Starlette deprecation as at the baseline)
- Reproducibility: a second full run of `models/eval_smd.py` (to a scratch file, at `b0f139c`) gave the same report except the "EternalAI commit of the script" line

## Live evidence
- Not live verified. This is an offline evaluation on public, anonymised data (SMD); EternalAI's live loop was not run,
  and nothing was wired into the engine.

## Dependencies and configuration changes
- None. Only numpy and pandas (already in `requirements-dev.txt`) and the standard library.
- One-time network access to `api.github.com` (file list) and `raw.githubusercontent.com` (files).
- Run time: about 18 minutes for the evaluation on this machine; memory about 100 MB (one machine at a time).

## Known limitations (what this does not show)
- Offline, on anonymised and normalised data; not EternalAI's live detector (which adds an isolation forest and
  per-service persistence); not a live check.
- SMD metrics cannot be named, so the plan's "CPU > 90%" cannot be applied; `FT` is a train-derived stand-in.
- 446 of the 1,064 metric series (42%) had a train robust scale below 0.01, so their floor was raised to 0.01 by the
  pre-registered rule; the results depend on that rule.
- The `upper` rules cannot catch drops.
- The plan's z-score constants were set for a 2-second loop; SMD has one row per minute.
- The plan's "20 series" is not reproduced: NAB (17 series, PR #1) and SMD (28 machines) are evaluated separately; the
  SMD event count does match the plan's 327.

## Shared-file integration requests (for Claude)
- None new. The engine wiring proposed in `docs/handback/rajat.md` still applies; these results suggest that, if
  wired, the z-score path should need agreement from at least 2 signals (as `Z-k2`) or the engine's existing
  persistence, to keep false alarms down. Proposal only.
- No bug found in the PR #1 files.

## Submission
- Push of `team/rajat-smd-eval` is **not authorised yet** (only on Prem's "push team/rajat-smd-eval"). Nothing pushed.
- Bundle for Prem (not yet created or sent):
  `git bundle create "$HOME\Desktop\team-rajat-smd-eval.bundle" 121024fa007ae5b0fc9dc8e0638c1e2b1cf6373a..team/rajat-smd-eval`
- After authorisation: PR from `team/rajat-smd-eval` to `plan-complete`.

## Suggested integration order and rollback
- Integration: after PR #1 (`team/rajat-zscore-nab`), since this branch builds on it. All paths are new files owned by
  Rajat.
- Rollback: Claude merges with `git merge --no-ff`; if needed, `git revert -m 1 <merge commit>` undoes it without
  rewriting history.
