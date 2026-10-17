# Run every benchmark arm in turn (5 repetitions per scenario). Resumable: finished (arm, scenario, seed) rows are skipped.
#   powershell -File scripts\run_all_arms.ps1
# Requires Docker Desktop and the images built (docker compose --profile releases build).
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"
$env:OMP_NUM_THREADS = "1"
$py = ".venv\Scripts\python.exe"
foreach ($arm in "eternalai_autopilot", "eternalai_ask_first", "threshold_restart", "prototype_rules", "no_action") {
    "$(Get-Date -Format s) start arm $arm" | Add-Content runtime\benchmark_progress.log
    & $py scripts\run_benchmark.py --arm $arm --reps 5 --manage-stack 2>&1 | Add-Content runtime\benchmark_progress.log
    "$(Get-Date -Format s) end arm $arm" | Add-Content runtime\benchmark_progress.log
}
"$(Get-Date -Format s) all arms finished" | Add-Content runtime\benchmark_progress.log
