# Post-benchmark runbook (self-contained)

Written 2026-10-18 while benchmark v1 was running, so that a new session can continue from this file alone. It records procedures, not results. Every number that ends up in a document must come from a rerunnable script and a file under `docs/results/` or `results/`.

## NEW SESSION START (do this first, and change nothing)

1. Read `docs/EVALUATION_PLAN.md` completely, including **Amendments 1, 2 and 3**, and this file.
2. Run (read-only): `D:\eAI\eAI-workspace\eAI\.venv\Scripts\python.exe scripts\benchmark_status.py --raw D:\eAI\eAI-workspace\eAI\docs\results\benchmark_raw.jsonl --log D:\eAI\eAI-workspace\eAI\runtime\benchmark_progress.log` (from `D:\eAI\eAI-docs`). It prints completed runs out of 225, per-arm and per-scenario counts, heartbeat and process state.
3. Do **not** start, stop or reset anything. Report to the user: the completed-run count, whether the benchmark process is alive, and which runbook step is next. Then wait for instructions.
4. Until the gate in step 0 passes: do not read `benchmark_raw.jsonl` content, do not run any Docker command, do not touch the evaluator volume, `.env`, or the main tree's `eternalai/ evaluator/ app/ models/ loadgen/ telemetry/ docker-compose.yml scripts/run_benchmark.py scripts/run_all_arms.ps1`.

## Where things are

| what | where |
|---|---|
| main tree (benchmark runs here) | `D:\eAI\eAI-workspace\eAI`, branch `main`; results file `docs/results/benchmark_raw.jsonl` (untracked until exported), progress log `runtime/benchmark_progress.log` |
| docs worktree (all documentation and tooling work) | `D:\eAI\eAI-docs`, branch `docs-prep`; publish with `git push origin docs-prep:main`, one file per commit, never force-push |
| remote | https://github.com/py007105/eAI |
| tags | `models-v1` (frozen models), `benchmark-system-v1` (the system the benchmark runs; commit 245d3e7) |
| Python | `D:\eAI\eAI-workspace\eAI\.venv\Scripts\python.exe` |
| compose project | `eai`; evaluator truth volume `eai_truth` (only the evaluator mounts it, at `/truth`); brain runtime volume `eai_eternalai-runtime` (at `/srv/runtime`, evidence files in `/srv/runtime/evidence/`) |
| ports | dashboard 8050, brain API 8000, shop 8080, evaluator 8200, Prometheus 9090, Jaeger 16686 |
| seeds | training 1000+; benchmark 100-148 (seed = 100 + 10*rep + scenario index); smoke tests 2000+; forecast check 3000-3004 (smoke 3900, 3901); live LLM check 3500-3504 |

## Standing rules (from the project brief and the user's instructions)

- No retuning. Honest metrics only: every number from a rerunnable script, nothing claimed as passed unless seen. Missing data stays missing.
- The brain never sees ground truth; the LLM never generates or runs commands; only real actions.
- Secrets only via environment or `.env`; never print, log or commit a key; print presence only.
- Python only. Small commits, one file at a time, push after each. Never force-push. Shut down what you start. Ask before downloads over 2 GB and before anything destructive.
- **System change vs tooling fix.** Fixes to `scripts/` (preflight, launchers, renderer, baselines), docs and tests are tooling fixes: make them freely and say "tooling fix" or "docs fix" in the commit message. Any change to `eternalai/`, `evaluator/`, `app/`, `models/` or benchmark configs (`docker-compose.yml`, `telemetry/`, `scripts/run_benchmark.py`, `scripts/run_all_arms.ps1`) is a **system change**: it becomes v2, is proposed with scope and hours, needs the user's approval, runs on fresh seeds, and is reported beside v1 (v1 is never removed or replaced). Never mix the two in one commit.
- Wording rules (plan Amendments 1 and 3): the load generator's failed-request % is presented first as the independent measure; recovery is always "self-reported" and never "independently verified"; the benchmark LLM path is stated as "configured without keys (by construction); provider not recorded per row (design limitation, class c)", never as a verified "template only".

## Step 0. Gate (stop if any item fails)

1. `benchmark_status.py` (command above) shows **225 / 225**.
2. No benchmark process is running (`Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_benchmark|run_all_arms' }` returns nothing) and the status heartbeat is stale only because the run ended.
3. The code matches the tag: in the main tree, `git diff --stat benchmark-system-v1 -- eternalai evaluator app models loadgen telemetry docker-compose.yml scripts/run_benchmark.py scripts/run_all_arms.ps1` prints nothing. (`python scripts/preflight.py` also checks this.)
4. If fewer than 225 and the process died: do **not** improvise. Resume only if step 3 holds, using the same command as the original launch (`scripts/run_all_arms.ps1`, which skips completed `(arm, scenario, seed)` triples), and log the interruption with timestamps in `docs/results/benchmark_interruptions.md`. If the code differs from the tag, stop and ask.
5. The user's Docker approval is conditional on this gate; once it passes, Docker commands are allowed for the steps below.

## Step 1. Export before anything else (never reset first)

Create `results/benchmark-v1/` in the docs worktree, then copy:

- `D:\eAI\eAI-workspace\eAI\docs\results\benchmark_raw.jsonl` and `...\runtime\benchmark_progress.log` and any `docs/results/benchmark_interruptions.md`.
- The evaluator's truth files: `docker cp <evaluator-container>:/truth/. results/benchmark-v1/truth` (container id: `docker ps -q --filter label=com.docker.compose.service=evaluator`; if it is stopped, `docker compose up -d --no-deps evaluator` first). This contains one JSON per attempt plus `results.jsonl`.
- Optionally the brain's evidence files: `docker cp <brain-container>:/srv/runtime/evidence results/benchmark-v1/evidence` (needed for step 3).
- Write `results/benchmark-v1/SHA256SUMS` (`scripts/demo.ps1` contains the checksum code; or `Get-FileHash -Algorithm SHA256`), verify it, and commit the export (commit one archive plus checksums if the folder is large). Only then may any reset or recreate happen. Note: recreating the brain container loses its runtime volume only if the volume is removed; never `docker compose down -v` before this step is committed.

## Step 2. Verify completeness (script output, not eyeballing)

- 225 rows exactly: 5 arms x 9 scenarios x 5 repetitions; per-cell count 5 everywhere; no duplicate `(arm, scenario, seed)` (render accounting section 1 shows all of this).
- Every row carries `system_commit` and it is the benchmark commit; `brain_status.fallbacks_in_use` empty for the brain arms; model metadata identical across rows.
- Harness failures per plan section 6: compare the progress log and truth files against the criteria; list any failed attempts in `docs/results/harness_failures.json` (`arm, scenario, seed, attempt, criterion, evidence`); nothing is dropped.
- Anything abnormal is reported as found, not repaired. A run is only re-run under the plan's rule (same seed, both attempts kept).

## Step 3. Render, triage, post-mortems

1. `python scripts/render_results.py` from the docs worktree with `--raw` pointing at the exported copy; output `docs/results/benchmark.md`. Failed-request % and the consistency check come first; the banner states the LLM-path wording. Commit the file.
2. Every non-recovery on supported faults (the table in section 7 of the render) gets class (a) harness artifact, (b) system bug, (c) design limitation, per plan section 9, with a post-mortem in `docs/postmortems/` made from `scripts/postmortem_extract.py` (read-only skeleton; see its docstring) plus the evidence file, and an entry in `docs/postmortems/triage.json` (`arm, scenario, seed, class, evidence`). Re-render.
3. **Orders-crash row** (`docs/postmortems/crash-orders-seed100-v1.md`, incident `e5267f50`): read `evidence/e5267f50.json` and record the classifier's top class, its probability, the abstain threshold in force and the recorded reason; if the stored row lacks them, say so.
4. Coverage table: which `(fault, target service)` pairs occur in the 72 training runs (`data/runs/*.json` in the main tree; 71 used) versus the benchmark rows. If the benchmark crashed a target never crashed in training, class (c) (weak generalisation across targets); otherwise search for a bug and show the evidence.
5. Abstentions on supported faults, by target service, across all scenarios and arms: tabulate and report whatever it shows, including "no clustering".
6. Report the "metrics on which EternalAI is not ahead" list as rendered. Do not editorialise beyond the table.
7. Count timelines containing `report by <provider>` (rendered in section 1) and state it as consistency evidence only.

## Step 4. Forecast check (`docs/FORECAST_CHECK.md`)

Follow that file exactly: smoke runs on seeds 3900 and 3901 first, then the 20 runs (seeds 3000-3004 for `memory_leak`, `disk_fill`, `traffic_surge`, `good_deploy`) with the brain in **watch-only**. The analysis script (to be written and fixture-tested before the run, as tooling) computes lead times from raw data. Report each criterion as pass or fail, phrased as counts ("0 warnings in 5 healthy runs"). The same runs are the live watch-only verification (item 22): report executed actions per run (expected 0). Results go in `docs/results/forecast_check.md`, never into benchmark tables. A failure is reported as failed, not tuned away on these seeds.

## Step 5. Offline RCA baseline

`python scripts/offline_rca_baseline.py` (main-tree data path default is `data/runs` relative to the script's repo; pass `--runs D:\eAI\eAI-workspace\eAI\data\runs`). Writes `docs/results/offline_rca_baseline.md`, labelled offline and kept apart from the live arms. Its `main()` has not been run before; if it fails, fix it as a tooling fix and say so. The learned ranker's out-of-fold figure stays in `docs/results/models_cv.md` and is only cited, not recomputed.

## Step 6. Live LLM check (needs the new key: STOP and ask the user)

1. **Ask the user for the new Gemini key** (the old one should be rotated). Do not print it, do not read `.env` aloud; the user places it in `.env` (or sets the shell variable). Groq stays untested and labelled so.
2. Start the brain with the key (a normal `docker compose up -d` reads `.env`; the benchmark launcher blanks the keys, so do not use it for this).
3. Confirm key **presence** in the brain container without printing: `python scripts/preflight.py --require-llm-key` (it prints PRESENT/ABSENT only).
4. Run a small set of live incidents on non-benchmark seeds (3500-3504; e.g. crash, latency, error_spike, bad_deploy, disk_fill) and read each incident's report metadata from `GET /incidents` (`report_meta.provider`, latency, fallback reasons). Report: the schema-validity rate (responses accepted by the validator over calls made, with the counts), latency (min, median, max per call), and how often the template fallback was used and why. Also run `scripts/llm_smoke.py` if useful. These runs are excluded from every benchmark table.
5. State the number of calls honestly (a handful is a handful).

## Step 7. Preflight and the demo launcher, three times

For each of three repetitions: `docker compose down`, then `scripts\demo.ps1 -ConfirmReset` (export, reset scorecard, up, wait, preflight, open the dashboard); time each with `Measure-Command`; record any failure or flakiness verbatim (container not healthy, preflight FAIL line, dashboard not loading, approval refused). The launchers were written and syntax-checked only; expect to find bugs and fix them as tooling fixes. Also run one blind challenge end-to-end after the third repetition (start, ask-first approve, reveal) and note whether it behaved as `docs/DEMO.md` says. Report real timings and real failures; do not smooth them.

## Step 8. Documents from rendered tables only

Update `docs/EVALUATION.md` (results section), `README.md` (a results section linking the generated files, with numbers copied only from them), `docs/DEMO.md` (fill every `[[...]]` placeholder from `docs/results/benchmark.md`, `forecast_check.md`, `offline_rca_baseline.md`), `docs/QA_FOR_JUDGES.md` (same) and the Limitations list. Required statements in each: recovery is self-reported (independent measure: failed-request %); benchmark LLM path wording (Amendment 3); n = 5 per cell, no per-cell significance claims; one application; scripted faults; Groq untested; the forecast metric was not measured in benchmark v1. Regenerate, do not retype, any number. If a claim cannot be traced to a file, delete the claim.

## Step 9. Merge and diff against the tag

`origin/main` currently receives every docs commit via `git push origin docs-prep:main`, so main is expected to be a fast-forward of the benchmark tree's HEAD. In the main tree: `git fetch origin`, confirm `git merge-base --is-ancestor main origin/main`, then `git merge --ff-only origin/main`. Then list **exactly** how the tree differs from the tag: `git diff --stat benchmark-system-v1 HEAD` and `git diff --name-only benchmark-system-v1 HEAD`. Expected: documentation, `scripts/` tooling and tests only. Any file under `eternalai/ evaluator/ app/ models/ loadgen/ telemetry/ docker-compose.yml` in that list is a finding: report it and stop.

## Step 10. Release check

1. Secrets scan of the full history: search `git log --all -p` (and the working tree) for key shapes and names (`AIza`, `AQ.`, `gsk_`, `api_key`, `GEMINI_API_KEY=` followed by a value, `Bearer `, private keys). Use gitleaks only if it is already installed; do not download tools silently. Report counts and file names, never the matched text.
2. Confirm `.env` and the reference clones were never committed: `git log --all --diff-filter=A --name-only` filtered for `.env`, `*.env`, and the reference-clone folder names listed in `docs/REFERENCES.md`/`.gitignore`; confirm `.gitignore` covers them.
3. Clean-checkout test once more (fresh clone into an empty directory, `docker compose --profile releases build && up -d`, preflight). Delete only directories this runbook's session created, and only after asking.
4. Tag `v1.0` on the final commit and push the tag (`git tag -a v1.0 -m ...`; `git push origin v1.0`). Never move or delete existing tags.
5. Clean-up suggestions to offer (ask first): delete the old `C:\` OneDrive copy and `D:\eAI\eAI-clean-test`; remind the user to rotate the old Gemini key.

## Step 11. Stop points that need the user's approval

- Any **v2** (system change): bring the scope, the hours, and the evidence from triage; wait for approval. Candidate items already identified, proposals only: evaluator-side raw probe logging; storing confidence, abstention reason, novelty distance and report provider in incident rows; shuffled-label control on live data; a second application.
- The **new Gemini key** (step 6).
- Anything **destructive**: removing volumes (`docker volume rm`, `down -v`), deleting directories, resetting the scorecard (only after step 1 is committed), force operations, history rewrites.
- Docker access before the step-0 gate passes.

## Report format after each step

Facts first (what ran, the command, the exit status, the numbers from the generated file), then what failed or surprised, then the next step. If something did not run or could not be verified, say so.
