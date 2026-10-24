# Live demo checklist (judges), Sat 24 Oct 2026

**Build to demo: `demo-stable-1` (`49155ea`)**, from the worktree `D:\eAI\eAI-demo-stable-1`.
- Not the merged `plan-complete`, and not candidate `71eb2f5` (G4 and G6 failed there; see `docs/CURRENT_NUMBERS.md`).
- No code changes. The only additions are an `.env` copy (yours) and a compose override outside git.
- Every number below comes from tonight's rehearsal (`docs/results/demo_rehearsal_*.md`).

Rules during the demo:
- Never `docker compose down -v`; never delete a volume.
- Never show `.env` or the token on screen.
- Type the token **by hand** in the browser.

---

## 0. Before the demo (T-15 min)

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
- `git check-ignore` prints `.env` (so it can never be committed);
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

Expected: `done`, then the scorecard shows `runs 0`. Optional, for a clean incident list: start the stack fresh (0.3), which empties the brain's in-memory incidents.

**0.6 The token, for the commands below** (typed, never shown):

```powershell
$s = Read-Host "Approval token" -AsSecureString
$t = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
$H = @{ "X-Approval-Token" = $t }
```

**0.7 Browser:** open http://127.0.0.1:8050 and **reload it (F5) after every stack start**: a page left open from before a restart can stop updating, and in the rehearsal an approval was missed that way. Then **type** the same token into the token field. Don't change Mode or the kill switch in the dashboard; the commands below do that. The **Approvals** panel glows when something is pending, and the tab title shows a countdown.

**0.8 Free RAM with the stack up:** `python scripts\memguard.py`. The rehearsal had 2.4-2.6 GB free. **Under 1 GB: close more apps before the judges.**

---

## 1. The demo (one command per step)

| step | command (window A) | expected time | what appears on the dashboard | what you say |
|---|---|---|---|---|
| **a) crash on web → autopilot restart** | `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"crash","target":"web","timeout_s":150}'` | detected ~5 s (rehearsal 5.3 s); restart at once; verified recovered ~47 s after the crash (rehearsal 46.6 s) | web node turns red; incident card "down" on web; action `restart_service` on web, **low risk, autopilot**; verification **recovered**; web green again | "A low-risk fix like a restart runs on its own, and EternalAI then checks a real checkout works again before it calls it fixed." |
| **b) bad deploy on payments → ask-first → you approve** | first `Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $H -ContentType application/json -Body '{"mode":"ask-first"}'` then `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"bad_deploy","target":"payments","timeout_s":400}'` | detected ~26 s (rehearsal 26.3 s); the approval card appears ~35 s after the bad deploy; you have **300 s** to approve (rehearsal: approved after 58 s); verified recovered ~2 min after the bad deploy (rehearsal 115.6 s) | an approval card: `rollback_release` on **payments**, **high risk**, waiting; you press **Approve**; the rollback runs; verification **recovered** | "Rolling back a payment service is high-risk, and payments is protected, so EternalAI proposes the fix with its evidence and waits for a person. Nothing happens until I approve." |
| **c) kill switch: nothing executes** | ON: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $H -ContentType application/json -Body '{"on":true}'`; inject: `Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $H -ContentType application/json -Body '{"scenario":"crash","target":"web","timeout_s":90}'`; when the card shows "blocked", OFF: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $H -ContentType application/json -Body '{"on":false}'` then back to autopilot: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $H -ContentType application/json -Body '{"mode":"autopilot"}'` | detected ~5 s; the run ends ~10-20 s after the escalation, and the evaluator then restores web | mode **watch-only**, kill switch **ON**; incident on web, policy **"blocked - kill switch is on: nothing is executed"**, escalated, no action; after OFF + autopilot: mode autopilot | "One switch stops every automatic action, even low-risk ones. It's diagnosed and shown to a human, but nothing is executed." |
| **d) open the incident report** | `$i = Invoke-RestMethod http://127.0.0.1:8000/incidents; $i[-1].report \| Format-List` (or click the incident in the dashboard) | instant | the report panel: summary, evidence, the proposed runbook, policy verdict and verification | "Every incident keeps its evidence, the decision and the reason, and whether the fix was verified, so a person can check it afterwards." |

Notes:
- **Step b:** this commit's dashboard records the approver as **`dashboard`** (a fixed name), not your name. Say "approved in the dashboard". Payments needs approval in every mode (protected service).
- **Step c:** after kill switch OFF, the brain stays in watch-only until the `mode autopilot` command; that's by design. The rehearsal saw exactly this block: "kill switch is on: nothing is executed".
- **Not shown live:** memory leak (failed requests were higher with EternalAI than without) and Kubernetes (bonus only if Rajat's run is verified).

---

## 2. If a step fails

| symptom | what to do |
|---|---|
| a `/runs` command returns 403 | the token is wrong; redo 0.6 (type it again) |
| a `/runs` command returns 409 "run in progress" | wait until the previous run ends (about 1 minute), then repeat |
| step a: no incident after 30 s | check `Invoke-RestMethod http://127.0.0.1:8000/status`; if the brain doesn't answer, go to the fallback (results tables, `docs/CURRENT_NUMBERS.md`) |
| step b: no approval card | the brain may have diagnosed another cause; open the incident (step d) and explain what it decided. Never approve something you don't understand. |
| step b: the card expired (300 s) | say "unapproved proposals expire and are escalated to a human"; repeat only if time allows |
| mode change refused (409) | the kill switch is ON; run the OFF command first, then the mode command |
| dashboard says "Token contains invalid characters" | type the token by hand (don't paste) |
| free RAM under 1 GB or Docker stops | stop the live part; show `docs/CURRENT_NUMBERS.md` and the rehearsal report |

## 3. After the demo

```powershell
docker compose -p eai stop
Remove-Variable t, s, H
```

Never `down -v`. The `.env` copy in the worktree stays ignored by git; delete it if this worktree is no longer needed.
