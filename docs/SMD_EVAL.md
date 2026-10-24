# SMD detector evaluation: pre-registration (version 1)

Owner: Rajat (`team/rajat-smd-eval`). Plan references: §6.3, §9.1, §10.2 row D ("SMD server machines"), §18 "Detect"
and "False alarms", §22 rule 7. Gap row D6 (the SMD half; the NAB half is `docs/NAB_EVAL.md`).

**Status of this file.** Written and committed **before** any SMD file was downloaded or scored. Only repository
metadata (commit list, licence text, file list with sizes from the GitHub API) was read to write it. Nothing below may
be changed after the first real run. A different rule must be added as a new, separately dated "version 2" section,
and both versions must be reported.

**What this is.** An **offline evaluation on public data; not live verified.** It says nothing about EternalAI's live
loop, which is not run here.

---

## 1. Data

| item | value |
|---|---|
| source | OmniAnomaly repository, https://github.com/NetManAIOps/OmniAnomaly, folder `ServerMachineDataset` |
| pinned commit | `7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4` (`master` head, committed 2021-02-12 02:02 UTC, "Add files via upload") |
| licence | MIT: repository `LICENSE` ("Copyright (c) 2021 NetManAIOps-OmniAnomaly") and `ServerMachineDataset/LICENSE` ("Copyright (c) 2021 NetManAIOps-SMD") at the pinned commit |
| files | `ServerMachineDataset/{train,test,test_label,interpretation_label}/<machine>.txt` for the 28 machines below, and `ServerMachineDataset/LICENSE`: 113 files |
| size (GitHub API, before download) | 485,982,236 bytes in total (train 242,274,510; test 242,279,640; test_label 1,416,840; interpretation_label 10,174) |
| local path | `data/raw/smd/` (git-ignored by `data/raw/`, never committed); `data/raw/smd/MANIFEST.json` records URL, commit, size and SHA256 per file |
| download | `python data/download_smd.py --commit 7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4` |

### 1.1 Machines (all 28; none excluded)
`machine-1-1` … `machine-1-8` (8), `machine-2-1` … `machine-2-9` (9), `machine-3-1` … `machine-3-11` (11).

If any file cannot be downloaded or fails its checks, the missing files are listed and the scope is reduced in a new,
dated pre-registration section **before** scoring; it is never reduced silently.

### 1.2 File format and pre-processing
- `train/` and `test/`: one row per minute, 38 comma-separated numbers per row, no header. Metric `j` (1-based, as
  in `interpretation_label`) is column `j - 1`.
- `test_label/`: one `0` or `1` per test row. The script stops (no result) if the number of label rows differs from the
  number of test rows, or if a data file does not have exactly 38 columns.
- `interpretation_label/`: lines `start-end:m1,m2,...` (a row range and 1-based metric numbers).
- No resampling, smoothing, rescaling, interpolation or deduplication. SMD is already normalised by its publishers. A
  value that is not a finite number is passed to the detectors as missing (the z-score detector ignores it; the fixed
  threshold does not alarm on it).
- Train and test are separate files; test row `i` is minute `i` of the test period. Time for scoring is the row index
  (1 row = 1 minute).

### 1.3 Split
- **Train** (`train/`, unlabelled, treated as normal) is used **only** to (a) set the per-metric parameters of section
  2 and (b) prime the z-score baseline. It is never scored.
- **Test** (`test/` with `test_label/`) is scored in full, from its first row. No parameter is fitted on test data or
  on labels.

### 1.4 Events
- An **anomaly event** is a maximal run of consecutive `1`s in `test_label/<machine>.txt`; its start and end rows are
  both inclusive.
- The report gives the total number of events (per machine and pooled) and compares it with the plan's **327**
  (plan §10.2 row D, "20 series, 327 events"; the owner's workbook indexes 327 SMD events). Any difference is stated
  plainly; no attempt is made to reach 327.

## 2. Detectors

Each detector produces one alarm flag per test row and per machine, from 38 per-metric flags. For metric `j`,
`V_j` = its train values (finite values only).

Per-metric parameters, from train only (fixed rules, chosen without seeing any SMD values):
- robust noise `s_j` = the same rule as NAB (`models/eval_nab.robust_scale`): `1.4826 * median(|V_j - median(V_j)|)`;
  if 0, `std(V_j)` (population); if also 0, `1e-6 * max(1, |median(V_j)|)`;
- `floor_j = max(s_j, 0.01)`. The absolute minimum 0.01 (1% of SMD's normalised range) is added because SMD metrics
  that are constant in train would otherwise get a floor of 1e-6, so that any tiny change in test would alarm; this is
  decided here, before any SMD value is seen;
- `min_gap_j = 3 * floor_j`;
- train maximum `M_j = max(V_j)`.

### 2.1 Z-score, primary: `Z`
- `eternalai.zscore_detector.ZScoreDetector` at the plan's defaults, unchanged: z limit 3.0, streak 3, warm-up 15,
  baseline window 120 (plan §6.3, §9.1). One detector key per metric, `SignalConfig(floor_j, min_gap_j, "upper")`.
- **Normal-only baseline from train:** before the test rows, each metric's detector is fed the **last 120 train rows**
  (= the baseline window). This fills the warm-up, so test row 0 is already scored. These rows are not scored. After
  that the detector runs over the test rows in order with its own rule (it keeps learning only from values that did not
  look hot).
- Metric flag = `ZResult.anomalous`. **Machine alarm at a row: at least 1 of the 38 metrics is anomalous.**

### 2.2 Z-score, secondary: `Z-k2`
Identical to `Z`, but the machine alarms at a row only if **at least 2** metrics are anomalous. Reported next to `Z`;
it does not replace it.

### 2.3 Fixed threshold, primary baseline: `FT`
SMD metrics are anonymised and normalised, so the plan's "CPU > 90%" cannot be identified. Instead, per metric:
- `T_j = M_j + max(0.1 * |M_j|, 0.01)` (the train maximum plus 10%, and at least 0.01 above it);
- metric flag at a row = `value > T_j` (one row is enough; no streak);
- **machine alarm at a row: at least 1 metric flag.**

### 2.4 Fixed threshold, secondary baseline: `FT-3`
Same `T_j`, but a metric flag needs `value > T_j` on 3 rows in a row (the z-score rule's streak), so the comparison is
not won by the streak alone. Machine alarm: at least 1 metric flag. Reported next to `FT`; it does not replace it.

## 3. Scoring (the NAB definitions, no point adjustment)

Applied per detector per machine to the test rows, with the scoring helpers of `models/eval_nab.py` (imported):
- **Alarm event:** a maximal run of consecutive alarm rows; it starts at its first row.
- **Detected event:** an anomaly event with at least one alarm event whose start row lies inside it
  (`start <= t <= end`). An alarm event that started before an anomaly event is not a detection of it.
- **True alarm event:** an alarm event whose start lies inside an anomaly event. **False alarm event:** one whose start
  lies outside every anomaly event.
- **No point adjustment:** an anomaly event counts once however many alarms it holds; points are never relabelled;
  recall and precision are computed on events, never on points.

Metrics per detector, per machine and pooled over the 28 machines (sum the counts, then divide):
1. anomaly events, detected events, **event recall** = detected / events;
2. alarm events, true alarm events, false alarm events, **alarm-event precision** = true / (true + false);
3. **false alarms per day** = false alarm events / outside-days, where outside-days = (test rows outside every anomaly
   event) / 1440;
4. **delay** per detected event = first alarm-event start inside the event minus the event start, in rows (= minutes);
   median and range (min–max), per machine and pooled;
5. per machine also: train rows, test rows, missing values, number of metrics with `s_j < 0.01` (floor raised).

A ratio with a zero denominator is reported as `n/a`, never as 0 or 1.

### 3.1 Explanation score (pre-registered, secondary)
Tests plan §9.1's idea of naming the signals behind an alarm.
- An anomaly event's **metric list** = the union of the metric numbers of every `interpretation_label` line whose range
  (`start-end`, both inclusive, taken as test row indices exactly as written) overlaps the event. An event that no line
  overlaps has no list and is counted separately as "no interpretation".
- For a detected event, the **alarming metrics** are the metrics whose metric flag is true at the start row of the
  first alarm event inside the event.
- **Explanation hit:** at least one alarming metric is in the event's metric list.
- **Explanation score** = hits / detected events that have a metric list. Reported per detector (pooled), with the
  number of detected events without a list. For context the report also gives the number of interpretation lines and
  how many of them overlap no anomaly event (a check of the index convention, not a parameter).

## 4. Rules for the run
- Output: `docs/results/smd_detector_eval.md`, written only by `models/eval_smd.py`; no number is typed by hand. It
  records the input SHA256s and the EternalAI commit of the script.
- The script reads only `data/raw/smd/`, one machine at a time; it refuses to run if `MANIFEST.json` is missing, if its
  commit is not the pinned one, or if a file is missing or its SHA256 differs from the manifest.
- The comparison rule is fixed: all four detectors are reported side by side, per machine and pooled; no winner is
  declared on a single machine; no parameter or rule in this file is changed after looking at results.
- Report wording: "offline evaluation on public data; not live verified".

## 5. Known limitations (stated in advance)
- SMD is anonymised and normalised: no metric can be named (CPU, memory, ...), so the plan's fixed thresholds cannot be
  applied as written; `FT` is a train-derived stand-in.
- 38 metrics per machine with "at least 1 metric" makes false alarms more likely than for one signal; `Z-k2` is
  reported for that reason.
- The `upper` rules cannot catch drops.
- The plan's z-score constants were set for a 2-second loop; SMD has one row per minute.
- The z-score baseline keeps adapting during test (by design of the rule); the fixed threshold does not.
- Not EternalAI's live detector (which also uses an isolation forest and per-service persistence), not a live check.
