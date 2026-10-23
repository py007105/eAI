# NAB detector evaluation: pre-registration (version 1)

Owner: Rajat (`team/rajat-zscore-nab`). Plan references: §6.3, §9.1, §10.2 row D, §18 "Detect" and "False alarms",
§22 rule 7. Gap rows D1 (module), D5 (event-level method), D6 (NAB only).

**Status of this file.** Written and committed **before** the NAB data was downloaded and before any evaluation output
existed. Nothing below may be changed after the first real run. A different rule must be added as a new, separately
dated "version 2" section, and both versions must be reported.

**What this is.** An **offline evaluation on public data; not live verified.** It says nothing about EternalAI's live
loop, which is not run here.

---

## 1. Data

| item | value |
|---|---|
| source | Numenta Anomaly Benchmark, https://github.com/numenta/NAB |
| pinned commit | `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140` (NAB `master`, committed 2024-12-03, "chore: MIT License (#408)") |
| files | `data/realAWSCloudwatch/<series>.csv` for the 17 series below, and `labels/combined_windows.json` |
| local path | `data/raw/nab/` (git-ignored, never committed); `data/raw/nab/MANIFEST.json` records URL, commit and SHA256 per file |
| download | `python data/download_nab.py --commit ea702d75cc2258d9d7dd35ca8e5e2539d71f3140` |

Licence note: the assignment describes NAB as AGPL-3.0; at the pinned commit `LICENSE.txt` is the MIT licence (the
commit that changed it is the pinned one). Either way the data is not committed.

### 1.1 Series (all 17 files in `realAWSCloudwatch` at the pinned commit; none excluded)

| # | series | class |
|---|---|---|
| 1 | `ec2_cpu_utilization_24ae8d` | CPU |
| 2 | `ec2_cpu_utilization_53ea38` | CPU |
| 3 | `ec2_cpu_utilization_5f5533` | CPU |
| 4 | `ec2_cpu_utilization_77c1ca` | CPU |
| 5 | `ec2_cpu_utilization_825cc2` | CPU |
| 6 | `ec2_cpu_utilization_ac20cd` | CPU |
| 7 | `ec2_cpu_utilization_c6585a` | CPU |
| 8 | `ec2_cpu_utilization_fe7f93` | CPU |
| 9 | `ec2_disk_write_bytes_1ef3de` | other |
| 10 | `ec2_disk_write_bytes_c0d644` | other |
| 11 | `ec2_network_in_257a54` | other |
| 12 | `ec2_network_in_5abac7` | other |
| 13 | `elb_request_count_8c0756` | other |
| 14 | `grok_asg_anomaly` | other |
| 15 | `iio_us-east-1_i-a2eb1cd9_NetworkIn` | other |
| 16 | `rds_cpu_utilization_cc0c53` | CPU |
| 17 | `rds_cpu_utilization_e47b3b` | CPU |

Class rule (by file name only): **CPU** if the name contains `cpu_utilization` (CloudWatch CPU utilisation, in percent);
otherwise **other**.

### 1.2 Pre-processing
- Read `timestamp` and `value` columns; parse `timestamp` as a naive date-time (NAB's format); sort by timestamp
  (files are already sorted; sorting is a safeguard).
- No resampling, smoothing, scaling, interpolation or deduplication. A `value` that is not a finite number is passed to
  the detectors as missing (the z-score detector ignores it; the fixed threshold does not alarm on it).
- Labels: the windows for `realAWSCloudwatch/<series>.csv` in `combined_windows.json`, each `[start, end]`, both
  ends **inclusive**.

### 1.3 Split (NAB's probationary convention)
- `n` = number of rows. Probationary length `P = min(floor(0.15 * n), 750)` rows (NAB's `getProbationPeriod`; equal to
  `floor(0.15 * n)` for every series with `n <= 5000`). The **probationary period** is the first `P` rows; the
  **scored period** is the rest.
- The probationary period is used **only** for (a) detector warm-up and baseline, (b) setting the per-series parameters
  in section 2. It is never scored.
- A label window is **evaluable** if its start time is at or after the first scored timestamp. Windows that start inside
  the probationary period are **excluded** from every count, and listed with their number per series.
- No train/validation/test split beyond this; no parameter is fitted on scored data or on labels.

## 2. Detectors

All detectors see every row of the series in time order, from the first row (so the z-score warm-up and baseline form
inside the probationary period). They emit one alarm flag per row. Only rows in the scored period are scored.

### 2.1 Z-score, primary: `Z-up`
`eternalai.zscore_detector.ZScoreDetector` at the plan's defaults, unchanged: z limit 3.0, streak 3, warm-up 15, baseline
window 120 (plan §6.3, §9.1). One detector key per series. Alarm flag at a row = `ZResult.anomalous`.

Per-series parameters, from the probationary values `V` only (fixed rule, chosen without seeing any NAB values):
- robust noise `s = 1.4826 * median(|V - median(V)|)` (scaled MAD); if `s == 0`, `s = std(V)` (population); if that is
  also 0, `s = 1e-6 * max(1, |median(V)|)`;
- `floor = s`;
- `min_gap = 3 * s`;
- `direction = "upper"` (as the plan's rule and the benchmark port).

### 2.2 Z-score, secondary: `Z-two`
Identical to `Z-up` except `direction = "two_sided"`. Reported next to `Z-up`; it does not replace it.

### 2.3 Fixed threshold, primary baseline: `FT`
Alarm flag at a row = `value > T` (one row is enough; no streak).
- **CPU** series: `T = 90` (percent; plan §18 "CPU > 90%").
- **other** series: `T = q99 + (q99 - q50)`, where `q50`, `q99` are the 50th and 99th percentiles of the probationary
  values `V` (numpy `percentile`, default linear interpolation). Meaning: twice as far above the median as the top 1%
  of the probationary values.

### 2.4 Fixed threshold, secondary baseline: `FT-3`
Same `T` as `FT`, but the alarm flag needs `value > T` on 3 rows in a row (the same streak as the z-score rule), so the
comparison is not won by the streak alone. Reported next to `FT`; it does not replace it.

## 3. Events and metrics (no point-adjustment)

Definitions, applied per detector per series to the scored period:
- **Alarm point:** a scored row whose alarm flag is true.
- **Alarm event:** a maximal run of alarm points on consecutive rows. Its **start time** is the timestamp of its first
  row. An alarm point in the probationary period is not scored; an alarm run that crosses into the scored period
  starts at the first scored row.
- **Detected window:** an evaluable window with at least one alarm event whose start time lies inside it
  (`start <= t <= end`). An alarm event that started before a window is not a detection of that window.
- **True alarm event:** an alarm event whose start time lies inside an evaluable window.
- **False alarm event:** an alarm event whose start time lies outside every window (evaluable or excluded). Alarm
  events starting inside an excluded window are neither true nor false and are counted separately.
- **No point-adjustment:** a detected window counts once, however many alarm points or events it holds; alarm points
  are never relabelled, and a window is never "fully detected" because one point in it fired. Recall and precision are
  computed on events, never on points.

Metrics per detector per series, and pooled over all 17 series (sum the counts, then divide):
1. evaluable windows, excluded windows;
2. **detected windows / evaluable windows**, and **event recall** = detected / evaluable;
3. alarm events in total, true alarm events, false alarm events, alarm events in excluded windows;
4. **event precision** = true alarm events / (true alarm events + false alarm events);
5. **alarms per day outside labelled windows** = false alarm events / outside-days, where outside-days = (number of
   scored rows whose timestamp is outside every window) × (the series' median time step) in days;
6. **detection delay** per detected window = start time of the first alarm event that starts inside the window minus
   the window start, in minutes; reported as **median and range (min–max)** per series, and pooled over all detected
   windows;
7. per series also: `n`, `P`, time step, `floor`, `min_gap`, `T`, and the exact SHA256 of every input file.

A ratio with a zero denominator is reported as `n/a`, never as 0 or 1. Totals are reported for all 17 series, and
separately for the 10 CPU and 7 other series.

### 3.1 Plan comparison
The plan (§10.2 row D) says "20 series, 327 events". The report states the number of series and of windows (all,
evaluable, excluded) actually evaluated, and says plainly how they differ. No attempt is made to reach 20 / 327.

## 4. Rules for the run
- Output: `docs/results/nab_detector_eval.md`, written only by `models/eval_nab.py`; no number is typed by hand.
- The script reads only `data/raw/nab/`; it refuses to run if a file is missing or its SHA256 differs from
  `MANIFEST.json`.
- The comparison rule is fixed: both detectors' numbers are reported side by side, per series and pooled; no winner is
  declared on a single series; no parameter or rule in this file is changed after looking at results.
- Report wording: "offline evaluation on public data; not live verified".

## 5. Known limitations (stated in advance)
- NAB AWS series are univariate; EternalAI's live detector sees several signals per service at once.
- NAB windows are wide and begin before the labelled anomaly point, so delay from the window start is not delay from
  the anomaly's onset; an alarm early in a window counts as detected.
- The `upper` rules (`Z-up`, `FT`, `FT-3`) cannot catch drops; `Z-two` is reported for that reason.
- The SMD dataset (plan §10.2 row D) is roadmap and not evaluated here.
- The plan's z-score parameters (z 3, streak 3, warm-up 15, window 120) were set for a 2-second loop; NAB AWS data is
  sampled about every 5 minutes, so warm-up and window cover much longer times here.
