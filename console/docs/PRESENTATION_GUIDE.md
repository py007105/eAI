# EternalAI: presenter and operator guide

This console is a read-only viewer. Run injection, mode changes, and approvals belong to the existing backend/operator workflow. No credentials go into `console/` or its browser.

## What is covered

| Planned item | Console status | Limit |
| --- | --- | --- |
| Landing and service health | Implemented | Values require a reachable API |
| Live incident stages, evidence, policy, report | Implemented | Stages follow reported incident fields; they do not execute actions |
| Incident selection and investigation | Implemented | Returned records only; Follow latest is automatic, a selected incident stays selected |
| Before/after checkout, errors, p95 latency | Implemented | Missing backend measurements remain Not reported |
| Forecast | Conditional | Only shown when the incident contains forecast fields; not validated as an accurate prediction here |
| 2D/3D topology | Implemented | Dependencies, not live traffic; 2D remains available; 3D is optional |
| Approvals, safety, audit | Implemented, observational | Approve in the existing dashboard or configured Telegram bot |
| Evaluator status and reveal | Implemented on Live Incident | Paste a run ID; Check run, then Reveal result after scoring finishes |
| Evaluator scorecard | Implemented on Overview | Independently fetched; errors are not proof that the evaluator stopped |
| Recorded evaluations | Verified Results | Source-backed recorded results, separate from live telemetry |
| Telegram | Integration evidence displayed | Requires the separately configured bot; this UI cannot establish current bot connectivity |
| Kubernetes | Offline-validation disclosure | No live cluster claim |
| All engine/release acceptance gates | Not complete | CURRENT_NUMBERS records G4/G6 failures and no demo-stable-2 promotion |

The UI covers the core presentation plan. It does not make the full backend roadmap complete. Keep the documented caveats for unseen faults, forecast uncertainty, dataset results, and unpromoted builds.

## Prepare before judges arrive

1. Use the already-rehearsed backend checkout `demo-stable-1` (`49155ea`), as specified in `docs/DEMO_CHECKLIST.md`. Do not substitute the current console branch as the backend deployment. Read `docs/COORDINATION.md` first: its atomic Docker lock procedure supersedes the checklist's older FREE-line check. A FREE display alone is not ownership.
2. Start and restock the backend using that checklist, with the owner-provided configuration and the shared lock. Aim for at least 3 GB available before stack startup. The operator must keep tokens off screen. Do not change any protected branch/tag or remove volumes.
3. Start the console in its own terminal:

   ```powershell
   cd D:\eAI\eAI-console\console
   npm ci
   npm run build
   $env:VITE_API_TARGET = "http://127.0.0.1:8000"
   npm run preview -- --port 4173 --strictPort
   ```

4. Open `http://127.0.0.1:4173/console/live`. Confirm **Live**, verify the mode/kill switch in Overview, and ensure services report current health. Preload Topology once if you plan to show 3D, then return to Live Incident. Use 2D on a low-memory laptop.
5. Keep the operator dashboard (`http://127.0.0.1:8050`) available for approvals, or run the separately configured Telegram bot using checklist step 0.7. The console itself has no token field.
6. Check the real approval TTL. The default is 120 seconds; the rehearsed external override was 300 seconds. Do not assume the override exists.

Read-only checks from the operator terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/status | Select-Object mode, kill_switch
Invoke-RestMethod http://127.0.0.1:8200/health
```

## How the presentation looks

| Screen | Presenter action | Explain |
| --- | --- | --- |
| Landing, about 20 seconds | Select a service in the documented architecture | “EternalAI connects detection, evidence, policy, and recovery verification.” |
| Overview, about 20 seconds | Show health, mode and kill switch | “These values come from the running system.” |
| Live Incident | Use Focus view, keep Follow latest selected | “The evaluator will inject a real fault into our local application.” |
| Incident pipeline | Watch Detect → Diagnose → Policy → Fix → Verification | “A low-risk allowed action can execute automatically. Execution alone is not proof of recovery.” |
| Recovery evidence | Compare the measured before/after rows | “These checkout probes and measurements show what recovered.” |
| Evaluator run | Paste the returned run ID; Check run until finished; Reveal result | “The evaluator kept the ground truth separate until scoring finished.” |
| High-risk incident | Show the waiting approval, approve through Telegram/dashboard | “Protected actions require a person's decision.” |
| Full investigation / Audit | Select the incident and inspect its trace | “The evidence, action and outcome remain reviewable.” |

For a short slot, show **crash then bad deployment**. Budget roughly 5–7 minutes including settling/approval; these are rehearsal estimates, not promises. For a longer slot use the rehearsed order **crash → kill-switch/disk-fill → bad deployment → report**. Bad deployments can add about 200 seconds of settling before the next run, so put them last. Exit Focus view with its button or Escape.

## Inject a real problem manually (PowerShell)

Use these only against your local, isolated hackathon stack. The evaluator injects real failures into the service containers, then scores and restores them. It needs the **approval token**, not the CHAOS_TOKEN. It manages CHAOS_TOKEN internally.

Create the request header once, without displaying the token:

```powershell
$secure = Read-Host "Approval token" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $headers = @{ "X-Approval-Token" = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
```

### 1. Web crash → automatic restart

Verify kill switch is OFF and mode is autopilot. The checklist establishes that state; if required, the operator can set it explicitly:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $headers -ContentType application/json -Body '{"on":false}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $headers -ContentType application/json -Body '{"mode":"autopilot"}'
$run = Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $headers -ContentType application/json -Body '{"scenario":"crash","target":"web","timeout_s":150}'
$run.run_id
```

The fault normally begins after about 45 seconds of settling. The earlier rehearsal measured detection about 6 seconds after injection and verified recovery about 47 seconds after injection. Watch the actual values; do not promise these timings. Paste `$run.run_id` into **Evaluator run** on Live Incident.

Before starting another run, check that the evaluator is finished (a recovered incident alone does not mean evaluator restoration finished):

```powershell
Invoke-RestMethod "http://127.0.0.1:8200/runs/$($run.run_id)/status"
# Only once state is finished:
Invoke-RestMethod "http://127.0.0.1:8200/runs/$($run.run_id)/reveal"
```

### 2. Optional kill-switch proof → disk fill

Run this before the bad deployment. Turn the kill switch ON, inject disk fill, and wait for the incident's actual blocked verdict. Show Safety and the incident record. Then turn it OFF and restore autopilot; switching OFF alone leaves the engine in watch-only.

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $headers -ContentType application/json -Body '{"on":true}'
$run = Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $headers -ContentType application/json -Body '{"scenario":"disk_fill","target":"web","timeout_s":150}'
$run.run_id
# After you have shown the blocked decision:
Invoke-RestMethod -Method Post http://127.0.0.1:8000/killswitch -Headers $headers -ContentType application/json -Body '{"on":false}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $headers -ContentType application/json -Body '{"mode":"autopilot"}'
```

If the system abstains instead of producing the expected policy verdict, explain the actual result. Do not claim a blocked runbook was observed. Wait for this evaluator run to finish before continuing.

### 3. Payments bad deployment → human-approved rollback

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/mode -Headers $headers -ContentType application/json -Body '{"mode":"ask-first"}'
$run = Invoke-RestMethod -Method Post http://127.0.0.1:8200/runs -Headers $headers -ContentType application/json -Body '{"scenario":"bad_deploy","target":"payments","timeout_s":400}'
$run.run_id
```

Wait for the actual `rollback_release` proposal on payments, inspect its evidence, then approve it in the configured Telegram bot. If Telegram is unavailable, use the existing operator dashboard. Return to the console to show the approval channel, execution and verification. An expired/rejected/partial/unresolved result must remain visible as such. This run may take longer due to settling and the approval window.

### Blind challenge boundary

The current evaluator's empty-body random pick includes **cpu_burn**, an unseen fault with a documented wrong-service restart in seed 426. Do not use `POST /challenge/start` or an empty `/runs` body for a supported-fault-only presentation. Instead, have a teammate choose one rehearsed supported scenario privately and issue its explicit `/runs` command. Give the presenter only the returned run ID. The evaluator will mark it `blind: false` because the operator specified the scenario; describe it accurately as **operator-selected, hidden from the presenter**, not an evaluator-random run. The console reveal remains unavailable until scoring finishes. Present cpu_burn separately, in ask-first mode, with the recorded limitations; it is not a reliable recovery showcase.

## If something fails

- **Partial/disconnected:** the affected panels suppress current values. Check API health and the preview proxy; do not narrate historical samples as live.
- **403:** re-enter the approval token. Do not put it into frontend files.
- **409 run in progress:** check the current run's status and wait for restoration. Do not launch overlapping injections.
- **failed evaluator state:** inspect the evaluator error/restoration before starting another run.
- **No incident at 60 seconds from the command:** check run status; the evaluator may still be settling. Fault injection is not immediate.
- **Report says template:** say deterministic report. Do not call it an LLM-generated report.
- **Backend unavailable:** show recorded results and identify them as recorded. No live recovery claim.

After the last run is finished, clear the terminal header variables: `Remove-Variable headers, secure, ptr`. Follow the existing checklist and coordination lock procedure for stopping your own stack. Never remove volumes.

## Verification of this UI change

This environment does not have the owner's running Docker backend. New interactive behavior is checked with test-only fixtures under `console/tests/`; those screenshots are not live evidence. The earlier `HANDOFF.md` records separate real runs against demo-stable-1. Rehearse the changed build against that backend before presenting.
