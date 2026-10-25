# Dry run 1 start (outside git): DEMO_CHECKLIST.md 0.3-0.5 on demo-stable-1 + the REST Telegram bot.
# Tokens are generated here per run and never printed: the approval token goes only to D:\eAI\demo\dryrun1.token (for the
# owner to type in the dashboard) and to the brain, evaluator and bot through environment variables.
$py = "D:\eAI\eAI-workspace\eAI\.venv\Scripts\python.exe"
$env:PATH = "D:\eAI\eAI-workspace\eAI\.venv\Scripts;C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH
$log = "D:\eAI\demo\dryrun1.log"
function L($m) { Add-Content $log "$(Get-Date -Format 'h:mm:ss tt') $m" }
L "start"
$appr = (& $py -c "import secrets;print(secrets.token_urlsafe(24))").Trim()
$chaos = (& $py -c "import secrets;print(secrets.token_urlsafe(24))").Trim()
[IO.File]::WriteAllText("D:\eAI\demo\dryrun1.token", $appr)
& $py -c "import sys;sys.path.insert(0,r'D:\eAI\eAI-release\scripts');import stack_lock;stack_lock.take('main','dry run 1 on demo-stable-1 (owner present, Telegram bot)','demo-stable-1@49155ea')"
if ($LASTEXITCODE -ne 0) { L "STOP: could not take the Docker lock"; exit 1 }
L "lock taken"
Set-Location D:\eAI\eAI-demo-stable-1
$env:CHAOS_TOKEN = $chaos; $env:ETERNALAI_APPROVAL_TOKEN = $appr; $env:EAI_EVALUATOR_TOKEN = $appr
$env:OTEL_SDK_DISABLED = "true"; $env:ETERNALAI_MODE = "autopilot"; $env:ETERNALAI_POLICY_FILE = ""
$env:GEMINI_API_KEY = ""; $env:GROQ_API_KEY = ""
docker compose -p eai --profile releases build 2>&1 | Out-Null; L "build exit $LASTEXITCODE"
$svc = docker compose -p eai config --services | Where-Object { $_ -ne "jaeger" }
docker compose -p eai -f docker-compose.yml -f D:\eAI\demo\compose.demo-ttl300.yml up -d --force-recreate $svc 2>&1 | Out-Null
L "up exit $LASTEXITCODE"
for ($i = 0; $i -lt 80; $i++) { try { $s = Invoke-RestMethod http://127.0.0.1:8000/status -TimeoutSec 5; if ($s.policy) { break } } catch {}; Start-Sleep 3 }
L "brain answers /status"
Start-Sleep 45
$r = & $py scripts\stock_gate.py --restock --force 2>&1 | Select-Object -Last 1; L "restock exit $LASTEXITCODE"
# 0.5 scorecard: copy out with checksums, then rename (nothing deleted)
$stamp = Get-Date -Format yyyyMMdd-HHmm
docker compose -p eai cp evaluator:/truth "D:\eAI\demo\scorecard-before-$stamp" 2>&1 | Out-Null
Get-ChildItem "D:\eAI\demo\scorecard-before-$stamp" -Recurse -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "{0}  {1}" -f $_.Hash.ToLower(), $_.Path } | Set-Content "D:\eAI\demo\scorecard-before-$stamp.SHA256SUMS"
$mv = docker compose -p eai exec -T evaluator sh -c "test -f /truth/results.jsonl && mv /truth/results.jsonl /truth/results-before-demo-$stamp.jsonl; echo done"
L "scorecard: copied to D:\eAI\demo\scorecard-before-$stamp (+SHA256SUMS); rename: $mv"
# 0.4 checks
$s = Invoke-RestMethod http://127.0.0.1:8000/status
$ttl = (docker compose -p eai exec -T eternalai printenv ETERNALAI_APPROVAL_TTL_S).Trim()
$sc = Invoke-RestMethod http://127.0.0.1:8200/scorecard
$free = (& $py -c "import sys;sys.path.insert(0,r'D:\eAI\eAI-release\scripts');import memguard;print(round(memguard.free_ram_gb(),2))").Trim()
L "checks: mode=$($s.mode) kill_switch=$($s.kill_switch) rulebook=$($s.policy.file) ttl=$ttl scorecard_runs=$($sc.runs) free_ram_gb=$free"
# Telegram bot (REST-only, Sanskar 4bdb017), no code change
foreach ($line in Get-Content D:\eAI\demo\telegram.env) { if ($line -match '^\s*([A-Z_]+)\s*=(.*)$') { Set-Item "Env:$($Matches[1])" $Matches[2].Trim() } }
$env:BACKEND_URL = "http://127.0.0.1:8000"
$b = Start-Process -FilePath $py -ArgumentList "-u", "-m", "eternalai.notify.bot" -WorkingDirectory D:\eAI\eAI-telegram -WindowStyle Hidden -RedirectStandardOutput D:\eAI\demo\bot.out.log -RedirectStandardError D:\eAI\demo\bot.err.log -PassThru
Set-Content D:\eAI\demo\bot.pid $b.Id
L "bot started PID $($b.Id)"
L "STACK UP"
