# One-command demo launcher (Windows PowerShell). WRITTEN, NOT YET RUN: rehearse it before relying on it.
#
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -ConfirmReset
#
# Condition: T3 (OTEL_SDK_DISABLED=true, no Jaeger), identical to the v2 collection and evaluation; the dashboard is the documented difference.
# Steps: refuse if a benchmark is running -> export results (and checksum) -> reset the scorecard -> start the stack -> preflight -> open the dashboard.
# The reset deletes the evaluator's volume (eai_truth). It runs only with -ConfirmReset AND only after the export has produced SHA256SUMS.
param([switch]$ConfirmReset, [string]$Project = "eai", [string]$ExportDir = "results/benchmark-v2")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "run_benchmark|run_all_arms|stage3_eval|stage3_rerun|ask_first_guard" }) {
    throw "a benchmark process is running; refusing to touch the stack"
}

# 1. export (never reset first)
$truth = "$ExportDir/truth"
New-Item -ItemType Directory -Force $truth | Out-Null
$ev = docker ps -q --filter "label=com.docker.compose.service=evaluator" | Select-Object -First 1
if ($ev) { docker cp "${ev}:/truth/." $truth } else { Write-Host "evaluator not running: skipping truth export (nothing to export from a stopped stack)" }
foreach ($f in "results/benchmark-v2/benchmark_v2_raw.jsonl", "docs/results/benchmark_raw.jsonl") { if ((Test-Path $f) -and ((Resolve-Path (Split-Path $f)).Path -ne (Resolve-Path $ExportDir).Path)) { Copy-Item $f $ExportDir -Force } }
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
# telemetry condition T3 (Amendment 4, Stage 0): trace exporter off, Jaeger NOT started. The dashboard IS started for the demo: a documented difference
# from the evaluated condition (it was not running during evaluation); the rehearsal in docs/DEMO.md checks that it does not change the brain's behaviour.
$env:OTEL_SDK_DISABLED = "true"
$services = docker compose -p $Project config --services | Where-Object { $_ -ne "jaeger" }
docker compose -p $Project up -d $services
Write-Host "waiting 60 s for services"; Start-Sleep 60

# 3b. inventory stock (Amendment 8): the inventory service only subtracts stock and its volume survives the reset above, so a long evaluation or earlier demo
# leaves it low or at zero. Restock to the seeded level (direct SQL, harness action; see scripts/stock_gate.py) and verify through GET /items. Refuses on failure.
python scripts/stock_gate.py --restock --force
if ($LASTEXITCODE -ne 0) { throw "inventory restock failed; do not demo" }

# 4. preflight (non-zero exit stops the launcher; includes the inventory stock check)
python scripts/preflight.py --require-llm-key
if ($LASTEXITCODE -ne 0) { throw "preflight failed; do not demo" }

# 5. open
Start-Process "http://localhost:8050"
