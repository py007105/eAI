# Live demo checklist (judges), Sat 24 Oct 2026

**Build to demo: `demo-stable-1` (`49155ea`)**, from the worktree `D:\eAI\eAI-demo-stable-1`.
- Not the merged `plan-complete`, and not candidate `71eb2f5` (G4 and G6 failed there; see `docs/CURRENT_NUMBERS.md`).
- No code changes. The only additions are an `.env` copy (yours), a compose override outside git, and Sanskar's REST-only Telegram bot run unchanged from its own worktree (`D:\eAI\eAI-telegram`, `4bdb017`).
- Every number below comes from tonight's rehearsal and dry run 1 (`docs/results/demo_rehearsal_*.md`, `docs/results/dry_run_1_*.md`).

Rules during the demo:
- Never `docker compose down -v`; never delete a volume.
- Never show `.env`, `D:\eAI\demo\telegram.env` or any token on screen.
- Type the token **by hand** in the browser.

---

## 0. Before the demo

**Start the stack at least 3 minutes before the demo.** About 1 minute to start, 45 s to settle, then the restock.

**0.1 Memory and the Docker lock** (window A, PowerShell):

```powershell
cd D:\eAI\eAI-demo-stable-1
$env:PATH = "D:\eAI\eAI-workspace\eAI\.venv\Scripts;C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH
python scripts\memguard.py
Get-Content D:\eAI\STACK_LOCK.md -Tail 1
```

Expected:
- at least 3 GB free; if not, close browsers other than the dashboard, chat apps and IDEs;
- the last line starts with `FREE`; if it says `HELD`, someone else is using Docker, so stop and ask.

**0.2 `.env` in this worktree** (you copy it; nobody prints it):

```powershell
Copy-Item D:\eAI\eAI-release\.env D:\eAI\eAI-demo-stable-1\.env
git check-ignore .env
docker compose config -q
```

Expected:
- `git check-ignore` prints `.env`;
- `config -q` prints **nothing**. It fails with "set CHAOS_TOKEN" if that variable is missing.

**`.env` variables (names only):**
- `CHAOS_TOKEN`: required; a real secret, never `evaluator-only`.
- `ETERNALAI_APPROVAL_TOKEN`: required; never `change-me`. It's the token you type in the dashboard and use for the commands below.
- `GEMINI_API_KEY`, `GROQ_API_KEY`: optional. The LLM only rewrites the report text; actions never wait for it.

**0.3 Start the stack** (autopilot, approval window 300 s):

```powershell
$env:OTEL_SDK_DISABLED = "true"
$env:ETERNALAI_MODE = "autopilot"
docker compose -p eai --profile releases build
$svc = docker compose -p eai config --services | Where-Object { $_ -ne "jaeger" }
docker compose -p eai -f docker-compose.yml -f D:\eAI\demo\compose.demo-ttl300.yml up -d --force-recreate $svc
Start-Sleep 45
python scripts\stock_gate.py --restock --force
```

Expected:
- the build takes about 30 s when cached;
- `up` lists the containers as Started;
- the restock ends with a verified-stock line (exit 0).

`D:\eAI\demo\compose.demo-ttl300.yml` sets `ETERNALAI_APPROVAL_TTL_S=300`. The brain reads it (`eternalai/config.py`, line 33), but this commit's compose file does not forward it, so the override adds it. **Demo setting only: the default is 120 s.**

**0.4 Check: autopilot, kill switch OFF, 300 s window, rulebook:**

```powershell
Invoke-RestMethod http://127.0.0.1:8000/status | Select-Object mode, kill_switch
(Invoke-RestMethod http://127.0.0.1:8000/status).policy | Select-Object file, auto_allowed_risks, protected_services
docker compose -p eai exec eternalai printenv ETERNALAI_APPROVAL_TTL_S
```

Expected: `mode autopilot`, `kill_switch False`; `default.yaml`, `{low}`, `{payments}`; `300`.

**0.5 Scorecard: show only tonight's demo runs (nothing is deleted).**
The dashboard scorecard reads the evaluator's `/truth/results.jsonl`, a file inside the `eai_truth` volume.
- `POST /admin/reset` does **not** clear it (it only clears the brain's cooldowns, breakers and open incidents).
- A fresh stack does **not** clear it either (the volume survives).

So: copy the volume's contents out with checksums, then **rename** the results file. The scorecard starts at 0 runs, and the old rows stay inside the volume under a new name.

```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmm
docker compose -p eai cp evaluator:/truth "D:\eAI\demo\scorecard-before-$stamp"
Get-ChildItem "D:\eAI\demo\scorecard-before-$stamp" -Recurse -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "{0}  {1}" -f $_.Hash.ToLower(), $_.Path } | Set-Content "D:\eAI\demo\scorecard-before-$stamp.SHA256SUMS"
docker compose -p eai exec evaluator sh -c "test -f /truth/results.jsonl && mv /truth/results.jsonl /truth/results-before-demo-$stamp.jsonl; echo done"
Invoke-RestMethod http://127.0.0.1:8200/scorecard
```

Expected: `done`, then the scorecard shows `runs 0`.

**0.6 The token, for the commands below** (typed, never shown):

```powershell
$s = Read-Host "Approval token" -AsSecureString
$t = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
$H = @{ "X-Approval-Token" = $t }
```

**0.7 Telegram bot** (window B; primary approval in step b). Sanskar's REST-only bot, unchanged, from its own worktree:

```powershell
cd D:\eAI\eAI-telegram
foreach ($line in Get-Content D:\eAI\demo\telegram.env) { if ($line -match '^\s*([A-Z_]+)\s*=(.*)$') { Set-Item "Env:$($Matches[1])" $Matches[2].Trim() } }
$s = Read-Host "Approval token" -AsSecureString
$env:ETERNALAI_APPROVAL_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
$env:BACKEND_URL = "http://127.0.0.1:8000"
D:\eAI\eAI-workspace\eAI\.venv\Scripts\python.exe -u -m eternalai.notify.bot
```

Expected: one line, `REST Telegram bot started; polling backend http://127.0.0.1:8000 every 2s`. Leave window B open; Ctrl+C stops it.
- Only `TELEGRAM_USER_ID` (your account, `7769231832`) can approve.
- Approvals are recorded as `telegram:7769231832`; there's no username on the account.
- **The bot prints times in UTC:** "14:02:23 UTC" means 7:32:23 PM IST.

**0.8 Browser:** open http://127.0.0.1:8050 and **reload it (F5) after every stack start**: a page left open from before a restart can stop updating, and in the rehearsal an approval was missed that way.
- **Type** the same token into the token field.
- Don't change Mode or the kill switch in the dashboard; the commands below do that.
- The **Approvals** panel glows when something is pending, and the tab title shows a countdown.

**0.9 Free RAM with the stack up:** `python scripts\memguard.py`. Dry run 1 had 2.71 GB free; the rehearsal 2.4-2.6 GB. **Under 1 GB: close more apps before the judges.**

**Expected on screen before you start, not a fault:** one or two **"insufficient evidence"** incidents, escalated with no action.
- One appears about 1 minute after startup.
- Another appears after each run, when the evaluator rebuilds the web container.
- Say: **"That's EternalAI noticing a brief change it can't explain. It doesn't guess and doesn't act; it hands it to a person with the evidence."**

---

## 1. The demo (in this order: a → c → b → d)

Order matters. After the bad deploy (b), the evaluator waits about **200 s** before it injects the next fault, so b comes after c. a and c don't change a release.

| step | command (window A) | expected time | what appears | what you say |
|---|---|---|---|---|
| **a) crash on web → autopilot restart** | `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"crash","target":"web","timeout_s":150}'` | the fault comes ~45 s after the command; detected ~6 s later (dry run 5.9 s); verified recovered ~47 s after the crash (dry run 46.5 s) | dashboard: web red, incident "down", action `restart_service` (**low risk, autopilot**), verification **recovered**. Telegram: a message **without buttons** ("Policy: execute", "Verified healthy at … UTC") | "A low-risk fix like a restart runs on its own, and EternalAI then checks a real checkout works again before it calls it fixed." |
| **c) kill switch ON → disk fill → nothing executes → OFF** | ON: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $H -ContentType application/json -Body '{"on":true}'`; then `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"disk_fill","target":"web","timeout_s":150}'`; when the card shows "blocked": OFF `Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $H -ContentType application/json -Body '{"on":false}'` and back to autopilot `Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $H -ContentType application/json -Body '{"mode":"autopilot"}'` | the fault ~45 s after the command; diagnosed `disk_fill` ~7 s later | mode **watch-only**, kill switch **ON**; incident "disk_fill" on web, policy **"blocked - kill switch is on: nothing is executed"**, escalated, no action. After OFF + autopilot: mode autopilot | "One switch stops every automatic action, even a low-risk cleanup. It still diagnoses and shows it to a person, but nothing is executed." |
| **b) bad deploy on payments → ask-first → you approve on Telegram** | first `Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $H -ContentType application/json -Body '{"mode":"ask-first"}'`, then `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"bad_deploy","target":"payments","timeout_s":400}'` | pending ~80 s after the command (dry run 81 s); you have **300 s**; verified recovered ~25 s after the approval | Telegram: a message **with Approve / Reject**; tap **Approve**. Dashboard: approval card `rollback_release` on **payments**, **high risk**; then executed (`human:telegram:7769231832`) and **recovered**. **Backup:** if no Telegram message within 60 s of the card, press **Approve in the dashboard** (recorded as `dashboard`) | "Rolling back a payment service is high-risk, and payments is protected, so EternalAI proposes the fix with its evidence and waits for a person. I approve it from my phone." |
| **d) open the incident report** | `$i = Invoke-RestMethod http://127.0.0.1:8000/incidents; $i[-1].report \| Format-List` (or click the incident in the dashboard) | instant | summary, likely cause, the proposed runbook, alternative causes, missing information, evidence ids | "Every incident keeps its evidence, the decision and the reason, and whether the fix was verified, so a person can check it afterwards." |

Notes:
- **Step c:**
  - Why disk fill: in dry run 1 a crash with the kill switch on was diagnosed "insufficient evidence" (abstained), so the block wasn't shown. A disk fill is diagnosed reliably (rehearsal: diagnosed and then "blocked - kill switch is on: nothing is executed").
  - After OFF, the brain stays in watch-only until the `mode autopilot` command; that's by design.
- **Step b, dashboard backup:** this commit's dashboard records the approver as `dashboard`, not your name. Payments needs approval in every mode.
- **Not shown live:** memory leak (failed requests were higher with EternalAI than without) and Kubernetes (Rajat's run was not done).

---

## 2. If a step fails

| symptom | what to do |
|---|---|
| a `/runs` command returns 403 | the token is wrong; redo 0.6 (type it again) |
| a `/runs` command returns 409 "run in progress" | wait until the previous run ends (up to ~4 minutes after a bad deploy), then repeat |
| step a: no incident 60 s after the command | check `Invoke-RestMethod http://127.0.0.1:8000/status`; if the brain doesn't answer, go to the fallback (`docs/CURRENT_NUMBERS.md`, rehearsal report) |
| step c: the incident says "insufficient evidence" instead of "blocked" | say "it abstained, so nothing would run anyway"; turn the kill switch OFF and set autopilot as in step c |
| step b: no Telegram message within 60 s of the dashboard card | approve in the dashboard (backup) |
| step b: no approval card at all | the brain may have diagnosed another cause; open the incident (step d) and explain what it decided. Never approve something you don't understand. |
| step b: the card expired (300 s) | say "unapproved proposals expire and are escalated to a human"; repeat only if time allows |
| mode change refused (409) | the kill switch is ON; run the OFF command first, then the mode command |
| dashboard says "Token contains invalid characters" | type the token by hand (don't paste) |
| bot window shows a warning line | approve in the dashboard (backup) |
| free RAM under 1 GB or Docker stops | stop the live part; show `docs/CURRENT_NUMBERS.md` and the rehearsal report |

## 3. After the demo

```powershell
# window B: Ctrl+C stops the bot
docker compose -p eai stop
Remove-Variable t, s, H
```

Never `down -v`. The `.env` copy in the worktree stays ignored by git; delete it if this worktree is no longer needed.
