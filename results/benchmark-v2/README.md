# Benchmark v2 export (made at Stage 3 completion, before any reset or recreate)

- `benchmark_v2_raw.jsonl`: the 95 result rows of the reduced v2 plan (Amendment 4 section M), one per (arm, scenario, seed), seeds 200-318.
- `stage3_driver.log`, `stage3_events.log`: driver output; event log (one memory kill, one resume, orphan, health-gate note, watcher start).
- `orphans.json`: evaluator run `8e932d23e9` (disk_fill seed 204) finished after the driver died; it has no row and is EXCLUDED. It is still inside `truth_and_evidence.zip` (`truth/results.jsonl` and its run file), because nothing was deleted from the volume.
- `ask_first_guard.log`, `ask_first_guard2.log`: the ask-first validity guard (before and after the kill).
- `health_log.tsv`: external container health log from 2026-10-19 00:29:31 IST (not covering earlier runs; Amendment 7).
- `truth_and_evidence.zip`: `truth/` = full contents of the evaluator volume (also earlier training, smoke and v1 records) and `evidence/` = the brain's `/srv/runtime/evidence` as left by the last brain container.
- `SHA256SUMS`: checksums of the files above. `SHA256SUMS-archive-contents`: checksum of every file inside the zip.
