# EternalAI: 5-Minute Live Demo Script & Fallback Plan

This script guides the presenter through an exact, timed 5-minute live demonstration for hackathon judges, followed by contingency steps if local infrastructure fails.

---

## Pre-Flight Checklist (10 Minutes Before Demo)

1. **Host Environment**: Close all background apps (IDEs, video conferencing, extra browser tabs); verify > 2 GB free RAM (`python scripts\memguard.py`).
2. **Stack Running**: Verify `docker compose ps` shows 4 app services (web, orders, payments, inventory), Prometheus, brain, dashboard, and evaluator.
3. **Browser**: Open `http://localhost:8050` (Dash UI).
4. **Token & Mode**: Enter the approval token manually into the dashboard field. Select **Ask first** mode (verified when mode pill displays "Ask-first").
5. **Fallback Tab Ready**: Keep a browser tab or local player open to the fallback video / rehearsal screenshots.

---

## Timed 5-Minute Presentation Sequence

```
0:00 ─── [The Pitch & Context] ─── 0:45 ─── [Challenge & Recovery] ─── 2:30 ─── [Unseen Fault Abstain] ─── 3:45 ─── [Honest Numbers] ─── 4:30 ─── [Q&A Handover] ─── 5:00
```

### 1. Context & Architecture (0:00 – 0:45)
- **What to show**: Dashboard home page showing four healthy green services (`web`, `orders`, `payments`, `inventory`), zero open incidents, and the mode set to **Ask first**.
- **What to say**:
  > *"When microservices fail, engineers face alert storms, delayed diagnosis, and stressful late-night manual fixes. EternalAI is an autonomous operations assistant that closes the loop: observe, detect, predict, diagnose root cause, select safe runbooks, and verify recovery. It runs inside the cluster, observes live Prometheus telemetry every 2 seconds, and acts deterministically under strict policy."*
- **What the judge sees**: Clean topology map, real-time telemetry metrics, and the safety policy configuration.

---

### 2. Live Challenge: Anomaly to Verified Recovery (0:45 – 2:30)
- **What to click**: Under the **Demo mode** panel, click **Start hidden challenge**.
- **What happens behind the scenes**:
  - The independent evaluator selects a random supported scenario from its private truth vault (e.g. `memory_leak`, `disk_fill`, `crash`, `slow_service`, or `bad_deploy`).
  - Evaluator settles the stack (45 s wait), then injects the fault into the target service.
- **What to say while waiting for injection**:
  > *"The fault truth is isolated in an unmounted volume that EternalAI cannot see. The brain scrapes metrics, flags anomalous deviations against learned boundaries, and identifies the root cause service across the dependency graph."*
- **What happens on screen (approx. 12–18 s after injection)**:
  - The affected service turns amber/red on the dependency map.
  - An **Approval Queue** card appears with an audio ping and visual flash.
  - The card displays: Diagnosed Fault, Target Service, Proposed Runbook, Risk Level (Low/Medium/High), Confidence Score, and a 120-second expiration countdown.
- **What to say**:
  > *"EternalAI diagnosed the fault and ranked the safest fix from our outcome-ranked knowledge base. We are in Ask-first mode: the automation never acts without human authorization. The proposal has a 120-second time-to-live before expiring safely."*
- **What to click**: Click **Approve**.
- **What the judge sees**:
  - The action executes via Docker (e.g. `recreate_container` or `clear_temp_path`).
  - The service transitions to 'recovering'.
  - **Internal Verification**: EternalAI runs a synthetic checkout transaction through `web -> orders -> payments -> inventory`.
  - A green banner confirms: **"Verified by EternalAI's own synthetic checkout"**.
- **What to click**: Once the run indicator displays **finished**, click **Reveal**.
- **What to say**:
  > *"Recovery is not an assumption—our synthetic probe confirmed the end-to-end user path is functional. Clicking Reveal shows the ground truth from the evaluator, confirming the diagnosed target and showing the load generator's independently measured failed-request rate."*

---

### 3. Unseen Fault & Safe Abstention (2:30 – 3:45)
- **What to click**: Click **Start unseen-fault segment** (runs `cpu_burn`, which was never in the training set).
- **What to say**:
  > *"What happens when the system encounters a novel failure it was never trained on? Real systems must not guess blindly. In our offline training, `cpu_burn` was withheld entirely. We equipped the fault classifier with a nearest-neighbour novelty gate."*
- **What the judge sees**:
  - The metrics show abnormal CPU, but the classifier flags the window as novel or low confidence.
  - The incident is marked **insufficient_evidence** and escalated to humans without executing random, destructive actions.
- **What to say (Honest limitation)**:
  > *"In benchmark v2, EternalAI abstained correctly in 2 of 3 runs. In one run—seed 426—the novelty gate missed and restarted the wrong service (`inventory` instead of `orders`). We diagnosed this post-mortem and introduced a close-candidates abstention rule. We do not claim perfect omniscience; we engineer safeguards to constrain risk."*

---

### 4. Honest Numbers & Evidence Review (3:45 – 4:30)
- **What to show**: Navigate to or display the Headline Numbers table from `docs/pitch/PITCH.md`:
  - **18/18** supported recoveries in benchmark v2 autopilot [82%, 100% Wilson CI].
  - **1/24** false incidents opened on healthy runs (vs **6/24** for threshold restart baseline).
  - **0/24** harmful actions on healthy runs.
  - **Disk fill forecast**: 86.4 s median lead time (PASSED >= 30 s target).
  - **Memory leak forecast**: 18.3 s median lead time (**FAILED >= 30 s target**; reported transparently).
- **What to say**:
  > *"Every claim we make is backed by reproducible, committed test logs under `docs/results/`. Where our system failed—such as memory leak forecast lead time—we report the failure openly rather than burying it."*

---

### 5. Wrap-up & Q&A Transition (4:30 – 5:00)
- **What to say**:
  > *"EternalAI demonstrates that autonomous SRE operations can be safe, predictive, and verified without handing unconstrained terminal access to an LLM. The core is modular: Docker today, Kubernetes on Rajat's branch, and interactive Telegram bot integration on Sanskar's branch. We are ready for your questions."*

---

## Failure Contingency Plan (If the Live Demo Fails)

If a hardware crash, Docker stall, or network blip occurs during presentation:

| Failure Mode | Immediate Remediation | Presenter Script |
|---|---|---|
| **Host RAM < 1 GB / Docker Freeze** | Switch immediately to the backup video recording or browser tab with pre-captured rehearsal artifacts. | *"Our local laptop memory hit Docker limits during container recreation. Rather than restart the Docker engine, let's step through our recorded end-to-end rehearsal run and validated traces."* |
| **Dashboard Offline (`:8050`)** | Open PowerShell Window B and trigger challenge via terminal: `python scripts\demo_challenge.py start` | *"The Dash UI frontend dropped its connection, but the underlying EternalAI engine API on port 8000 is fully operational. We can execute and observe via the evaluator CLI."* |
| **No Proposal Appears (> 90 s)** | Wait for the evaluator run indicator to display finished; click **Reveal**. | *"The settle window for deploys can take up to 200 s. Let's inspect the evaluator's timeline to check whether an incident was detected or if the draw was a healthy control."* |
| **Accidental Wrong Action** | Show the incident audit log (`runtime/audit.jsonl`). | *"The policy engine recorded this intervention with full audit provenance. Here is how the cooldown and circuit breaker prevent repeat destructive attempts."* |

### Pre-Recorded Backup Video & Artifact Locations
- Rehearsal logs and timings: `docs/results/demo_rehearsal_R4.md` and `docs/results/demo_rehearsal_R5.md`
- Visual UI progression screenshots: `docs/screenshots/`
- Full benchmark evaluation: `docs/results/benchmark_v2.md`
