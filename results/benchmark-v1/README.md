# Benchmark v1 export (made before any reset or recreate; runbook step 1)

- `benchmark_raw.jsonl`: the 225 result rows (5 arms x 9 scenarios x 5 reps), copied from the main tree's `docs/results/benchmark_raw.jsonl`.
- `benchmark_progress.log`: the driver's progress log.
- `truth_and_evidence.zip`: `truth/` = the full contents of the evaluator volume (`/truth`: one JSON per attempt plus `results.jsonl`; it also holds earlier training-collection and smoke-run records, not only benchmark runs) and `evidence/` = the brain's `/srv/runtime/evidence` as left by the last brain container.
- `SHA256SUMS`: checksums of the three files above. `SHA256SUMS-archive-contents`: checksums of every file inside the zip (and the raw and log files), verified against the extracted archive with 0 mismatches.
- No `benchmark_interruptions.md` existed at export time. A pattern scan of the export for key shapes found 0 hits.
