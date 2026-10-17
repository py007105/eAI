# One-command demo launcher (Windows PowerShell). WRITTEN, NOT YET RUN: rehearse it before relying on it.
#
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -ConfirmReset
#
# Steps: refuse if a benchmark is running -> export results (and checksum) -> reset the scorecard -> start the stack -> preflight -> open the dashboard.
# The reset deletes the evaluator's volume (eai_truth). It runs only with -ConfirmReset AND only after the export has produced SHA256SUMS.
param([switch]$ConfirmReset, [string]$Project = "eai", [string]$ExportDir = "results/benchmark-v1")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "run_benchmark|run_all_arms" }) {
    throw "a benchmark process is running; refusing to touch the stack"
}

# 1. export (never reset first)
$truth = "$ExportDir/truth"
New-Item -ItemType Directory -Force $truth | Out-Null
$ev = docker ps -q --filter "label=com.docker.compose.service=evaluator" | Select-Object -First 1
if ($ev) { docker cp "${ev}:/truth/." $truth } else { Write-Host "evaluator not running: skipping truth export (nothing to export from a stopped stack)" }
if (Test-Path docs/results/benchmark_raw.jsonl) { Copy-Item docs/results/benchmark_raw.jsonl $ExportDir -Force }
$sums = Get-ChildItem $ExportDir -Recurse -File | Where-Object { $_.Name -ne "SHA256SUMS" } |
    ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.FullName.Substring((Resolve-Path $ExportDir).Path.Length + 1) }
Set-Content -Encoding ascii "$ExportDir/SHA256SUMS" $sums
Write-Host "exported $($sums.Count) file(s) with checksums to $ExportDir"

# 2. reset the scorecard
if (-not $ConfirmReset) { throw "export done; re-run with -ConfirmReset to delete the scorecard volume ${Project}_truth" }
if ($sums.Count -eq 0) { throw "nothing was exported; refusing to reset" }
docker compose -p $Project down
docker volume rm "${Project}_truth"

# 3. start
docker compose -p $Project up -d
Write-Host "waiting 60 s for services"; Start-Sleep 60

# 4. preflight (non-zero exit stops the launcher)
python scripts/preflight.py --require-llm-key
if ($LASTEXITCODE -ne 0) { throw "preflight failed; do not demo" }

# 5. open
Start-Process "http://localhost:8050"
