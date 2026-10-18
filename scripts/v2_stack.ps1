# Bring up the v2 stack under the pre-registered telemetry condition T3 (Amendment 4, Stage 0 result): OTEL_SDK_DISABLED=true, Jaeger and the dashboard NOT started.
#   powershell -File scripts\v2_stack.ps1 [-Brain none|watch-only|ask-first|autopilot|threshold_restart]
# Applies identically to the training collection, every evaluation arm and the baselines. No volume is removed; nothing is reset.
param([string]$Brain = "none")
$ErrorActionPreference = "Continue"      # docker writes progress to stderr; judge by exit codes instead
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
$env:OTEL_SDK_DISABLED = "true"
Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose stop jaeger dashboard *> $null
docker compose up -d --no-deps prometheus loadgen evaluator *> $null; if ($LASTEXITCODE) { throw "compose up (prometheus loadgen evaluator) failed" }
docker compose up -d --no-deps --force-recreate web orders inventory payments *> $null; if ($LASTEXITCODE) { throw "compose up (apps) failed" }
if ($Brain -eq "none") { docker compose stop eternalai *> $null; "brain: stopped (collection runs are no-action runs)" }
else { Write-Host "start the brain with scripts\startbrain.py or run_benchmark.py --manage-stack (it inherits OTEL_SDK_DISABLED from this environment only for compose calls made from this shell)" }
docker ps --format "{{.Names}} {{.Status}}"
