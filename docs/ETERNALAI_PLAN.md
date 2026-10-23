# EternalAI — Complete Project Context

> **Purpose of this file.** This is the single source of truth about EternalAI for any developer or AI coding assistant (CLI) working on the project. Read it fully before writing code. It explains the problem, the solution, the scope, what already exists (prototype v1), what we are building next (v2), the architecture, every AI component, the dataset, the tech stack, deployment, permissions, safety rules, the build plan and how we evaluate results.
>
> **Tip:** save it at the repository root as `CLAUDE.md` (or `AGENTS.md`) so coding assistants load it automatically.

---

## Table of contents

1. [One-paragraph summary](#1-one-paragraph-summary)
2. [Team and context](#2-team-and-context)
3. [The problem](#3-the-problem)
4. [The solution](#4-the-solution)
5. [Scope: what EternalAI handles and what it does not](#5-scope-what-eternalai-handles-and-what-it-does-not)
6. [Current prototype (v1): what already exists](#6-current-prototype-v1-what-already-exists)
7. [Target architecture (v2)](#7-target-architecture-v2)
8. [The loop, step by step: input → processing → output](#8-the-loop-step-by-step-input--processing--output)
9. [AI and ML components in detail](#9-ai-and-ml-components-in-detail)
10. [The dataset](#10-the-dataset)
11. [Tech stack](#11-tech-stack)
12. [How it runs in a real company (deployment)](#12-how-it-runs-in-a-real-company-deployment)
13. [Permissions (RBAC) and security](#13-permissions-rbac-and-security)
14. [Safety controls](#14-safety-controls)
15. [Interfaces: dashboard, API, notifications, configuration](#15-interfaces-dashboard-api-notifications-configuration)
16. [Build plan for the hackathon (v2)](#16-build-plan-for-the-hackathon-v2)
17. [Proposed v2 repository layout](#17-proposed-v2-repository-layout)
18. [Evaluation: how we measure and report results](#18-evaluation-how-we-measure-and-report-results)
19. [Demo script](#19-demo-script)
20. [Known limitations and honest numbers](#20-known-limitations-and-honest-numbers)
21. [How to answer common questions](#21-how-to-answer-common-questions)
22. [Rules for anyone writing code on this project](#22-rules-for-anyone-writing-code-on-this-project)
23. [Glossary](#23-glossary)
24. [Sources](#24-sources)

---

## 1. One-paragraph summary

**EternalAI is an autonomous operations system for backend servers — an on-call engineer that never sleeps.** It installs inside a company's own Kubernetes cluster, reads the health numbers the company already collects in Prometheus, and every 2 seconds it **detects** anything abnormal, **predicts** crashes before they happen, **finds the root-cause service**, **identifies the fault type** with a model trained on labelled fault data, **chooses the fix** that has measurably worked best, checks a **company rulebook** (automatic or human approval), **acts** through the Kubernetes API (restart, scale, roll back), **verifies** that the service and everything that calls it recovered, **explains** what happened in plain English on Slack/Telegram, and **learns** from every incident.

---

## 2. Team and context

| Item | Detail |
|---|---|
| Project | EternalAI |
| Team | **Brahmastra** — Mihir Pukale (leader), Rajat Raghatwan, Sanskar Randive |
| Current stage | Selected for **Hackyard Build 2026, IIT Guwahati** (top 300 of ~1,000 teams); offline 24-hour build on **24–25 October 2026** |
| Origin | First built for CodeAstra 2.0 (RGIT), problem statement CLOUD 3: *Autonomous Cloud Operations Platform* |
| Mentor feedback so far | (1) The fault-identification model must be **trained on data**, not hand-written rules. (2) A wrong code push is **human error** — we do not prevent it; we catch its effect in production. |
| Goal of the v2 build | Turn the working prototype (rules + anomaly detection on Docker) into a **generic, Kubernetes-native system with trained models** for fault identification, root cause and fix choice. |

---

## 3. The problem

Modern applications (shopping, payments, food delivery, banking) run as **many small backend services** (microservices) that call each other: `web → orders → payments → database`. When one breaks:

1. **Failures are found late.** Teams often learn from customers or from a pile of alerts minutes after the problem started.
2. **Alert storms hide the cause.** When `payments` slows down, `orders` and `web` also go red. Engineers get five alerts and must work out which service actually started it.
3. **Fixes are manual and slow.** Someone is paged, logs in, investigates, restarts or rolls back — often at night. Every minute of downtime costs money and users.
4. **Many failures are predictable.** A memory leak or a filling disk shows a steady trend minutes before the crash, but nobody acts until it breaks.
5. **Existing tools mostly alert; they rarely decide and act safely.** Monitoring shows graphs; Kubernetes restarts crashed pods blindly; neither says *"payments has a memory leak, restart it now with no downtime, and here is why."*

---

## 4. The solution

EternalAI closes the loop from **seeing** to **fixing**:

| Step | Plain words |
|---|---|
| Observe | Read 8 health signals per service every 2 s |
| Detect | Compare every signal with that service's own learned normal |
| Predict | Forecast when memory/disk/traffic will hit the limit |
| Root cause | Blame the deepest broken service in the call chain, not every red service |
| Identify | A trained classifier names the fault (memory leak, overload, bad deploy…) with a confidence score; low confidence = "unknown" → human |
| Choose fix | Knowledge base lists every fix; measured outcomes pick the best one |
| Rulebook | Company policy decides: run automatically, or ask a human (one tap) |
| Act | Kubernetes API: rolling restart, scale, rollback, cleanup |
| Verify | Re-check the service **and all its callers** 16 s later; retry once, then escalate |
| Explain | Plain-English report (built-in template or optional LLM) to Slack/Telegram/dashboard |
| Learn | Store incident + fix + result → new training data → retrain |

### Why this is not "just a wrapper"

- Kubernetes and Prometheus are **plumbing every DevOps tool uses** (eyes and hands). They never decide anything.
- The intelligence is ours: per-service anomaly detection (Isolation Forest + statistics), forecasting, root-cause ranking, a trained fault classifier, outcome-based fix ranking, safety policy and verification.
- **Test:** switch the LLM off completely → EternalAI still detects, diagnoses and fixes. The LLM only writes reports and suggests options for unknown faults.

### Measured proof (prototype benchmark, 59 runs, local processes, 2 vCPU)

| Fault | With EternalAI (Autopilot) | Without (Watch-only baseline) |
|---|---|---|
| Memory leak | 0/5 crashes, **0.2%** failed requests, fixed before limit | **3/3 crashed**, 23.9% failed |
| Disk filling | 0% failed | 22.1% failed |
| Error spike | 5.0% failed | 41.9% failed |
| Bad deployment | 3.9% failed (rollback) | 32.7% failed |
| Traffic surge (8 → 45 req/s) | 0% failed (scaled ahead) | 12.0% failed |
| Service crashed | 5.6% failed | 97.8% failed |
| Slow service (3-service cascade) | 2.9% failed | 5.7% failed |
| Runaway CPU | 0.7% failed | 0% failed (honest exception: restart cost a few requests) |

Median detection: 3.9–7.4 s for sudden faults; 16.6 s for traffic surge. These are **prototype results on injected faults**, not production guarantees.

---

## 5. Scope: what EternalAI handles and what it does not

**In scope = runtime faults of backend services: anything that shows up in the health signals while the application is running.**

### 5.1 Fault taxonomy (15 types in 6 groups + dependency handled by root cause)

| Group | Fault type (`fault_type` label) | Signals that show it | Default action |
|---|---|---|---|
| Resource | `memory_leak` | memory share rising steadily, traffic flat | Restart with helper copy (auto, low risk) |
| Resource | `cpu_runaway` | CPU near limit, traffic flat | Restart if users affected (auto, medium) |
| Resource | `disk_filling` | disk share rising | Clean temp files/logs (auto, low) |
| Resource | `resource_exhaustion` | errors up ("too many connections/open files"), CPU/mem normal | Restart; suggest pool/limit change |
| Availability | `crash` | up/down = down | Restart (auto, low) |
| Availability | `crash_loop` | restarts rising, CrashLoopBackOff | **Do not keep restarting**; roll back last change (approval) |
| Availability | `oom_kill` | memory hits 100% then restart (OOMKilled) | Restart; propose higher limit (approval) |
| Performance | `slow_service` | latency of one service up, callers slower | Restart root service; escalate if it persists |
| Performance | `overload` | traffic ≫ baseline, many services hot | Forecast + scale out ahead (auto, low) |
| Performance | `db_slowdown` | all DB users slow together | Flag DB as root; suggest fixes; **human always** |
| Network | `network_delay` | callers' client latency up, service's own latency flat | Suggest move pod / reroute (approval) |
| Network | `packet_loss` | intermittent errors/timeouts | Suggest (approval) |
| Network | `dns_failure` | many services fail outgoing calls at once | Restart/scale DNS (approval) |
| Deployment | `bad_deploy` | errors/latency jump within 5 min of a deploy | **Roll back, always with approval** |
| Deployment | `bad_config` | errors / pods not ready right after config change | Revert config (approval) |
| Deployment | `app_error` | error burst with no deploy, CPU/mem normal | Restart with helper copy; feature flag off; escalate |
| — | `normal` | nothing abnormal | none |
| Dependency | (role, not a type) | a called service is slow/down | Fix the **root** service only; callers are "victims" |

### 5.2 Out of scope (and why)

| Not handled | Why | What EternalAI does instead |
|---|---|---|
| Logic bugs (wrong price, wrong result) | No change in health signals | Nothing visible → nothing raised. Used only as test data for the "unknown" path (`logic_bug` label) |
| CI/CD pipeline failures (build/test breaks) | Happens before release, no customer impact | If a broken build gets deployed, it becomes `bad_deploy` → caught and rolled back |
| Front-end / user devices | Outside the servers | — |
| Security attacks | Separate domain with its own tools | — |
| Deleted data / human mistakes | Cannot be undone by automation | Detect in seconds, identify DB as root, escalate with restore-from-backup playbook. **Never auto-restore or write to a database** |

---

## 6. Current prototype (v1): what already exists

The prototype runs end-to-end on Docker Compose (or as local processes) with a demo 4-service shop.

### 6.1 Repository layout (v1)

```
eternalai/
├── docker-compose.yml        # web, orders, payments, inventory, loadgen, prometheus, brain
├── run_local.py              # same stack as local processes (no Docker)
├── prometheus/prometheus.yml # DNS service discovery of demo services
├── services/
│   ├── app.py                # demo microservice: /work, /metrics, /health, /chaos/<kind>, /deploy, /cleanup
│   ├── loadgen.py            # fake shoppers (configurable req/s)
│   └── discovery.py
├── brain/                    # EternalAI itself
│   ├── main.py               # Starlette API + dashboard server (port 8080)
│   ├── engine.py             # the loop, incidents, runbook, modes, approvals, verify
│   ├── sources.py            # PrometheusSource / DirectSource (scrape /metrics)
│   ├── store.py              # rolling history (15 min @ 2 s), histogram → p95
│   ├── detect.py             # ZScoreDetector + ForestDetector (Isolation Forest)
│   ├── predict.py            # time_to_limit (linear trend), holt_forecast, traffic_plan
│   ├── diagnose.py           # root-cause rule on TOPOLOGY + fault-kind rules
│   ├── drivers.py            # DockerDriver (Docker Engine API) / LocalDriver
│   ├── explain.py            # template report + optional Gemini/Groq LLM report
│   ├── notify.py             # Telegram
│   ├── config.py             # all settings (env-overridable)
│   └── static/               # dashboard (HTML/CSS/JS, SVG charts)
└── bench/run_bench.py        # benchmark: 8 faults × Autopilot vs Watch-only → runs.csv/jsonl, summary.md
```

### 6.2 Demo application

| Service | Calls | Base latency | Capacity |
|---|---|---|---|
| web (entry) | orders | 25 ms | 40 req/s |
| orders | payments, inventory | 45 ms | 24 req/s |
| payments | — | 35 ms | 70 req/s |
| inventory | — | 20 ms | 90 req/s |

Chaos endpoints on each service (`POST /chaos/<kind>`): `memory-leak`, `cpu-spike`, `errors`, `latency`, `disk-fill`, `crash`, `reset`. Bad deploy via `POST /deploy` (buggy v2). Services run with `restart: "no"` on purpose — EternalAI, not Docker, brings them back.

### 6.3 Key v1 parameters (from `brain/config.py`, `detect.py`, `predict.py`, `engine.py`)

| Parameter | Value |
|---|---|
| Loop tick | 2 s; history 450 points (15 min) |
| Z-score | z > 3 for 3 checks in a row; metrics p95, err, cpu, mem; warm-up 15 points; baseline only learns from normal values |
| Isolation Forest | features `[p95, err, cpu, mem_ratio, sat]`, 100 trees, `contamination="auto"`, score < −0.08 for 5 checks |
| Trend prediction | linear fit on last 8 points (16 s), require R² ≥ 0.8 |
| Holt forecast | α = 0.4, β = 0.15, 16 s ahead (8 steps) |
| Act margin | memory leak: act when ≤ 75 s left; disk: ≤ 60 s |
| Deploy window | errors within 300 s of a deploy → `bad_deploy` |
| Cooldown | 40 s per service; scale cooldown 10 s |
| Verify | 16 s after fix (+ up to 30 s grace), checks service **and all upstream callers** |
| Attempts | max 2 per incident, then escalate |
| Settle | 20 s after an action, symptom incidents suppressed |
| Replicas | min 1, max 3 (demo) |
| Modes | `watch` (recommend only), `ask` (every fix needs approval), `autopilot` (low/medium auto, high asks) |

### 6.4 v1 runbook (hand-written rules — to be replaced by trained models in v2)

| Kind | Action | Risk |
|---|---|---|
| memory_leak | restart (helper replica first) | low |
| disk_filling | cleanup | low |
| down | restart | low |
| overload / traffic_surge | scale_up / scale_to | low |
| cpu_runaway, error_spike, latency_spike | restart | medium |
| bad_deploy | rollback | high (always asks) |
| unusual (only Isolation Forest fires) | none — ask a human | none |

### 6.5 What is real ML in v1 vs rules

- **Real ML/statistics:** Isolation Forest, z-score baselines, linear-trend time-to-limit, Holt forecasting.
- **Rules:** root cause (deepest-sick-service rule), fault-kind decision, fix choice (runbook). **v2 replaces these with models trained on the dataset.**

---

## 7. Target architecture (v2)

### 7.1 Big picture

```
┌──────────────────────── COMPANY'S SYSTEM (already exists) ────────────────────────┐
│ Apps on Kubernetes: [web] → [orders] → [payments] → [database]                    │
│ Eyes: Prometheus (+ cAdvisor, kube-state-metrics, app/OTel metrics)               │
│ Control panel: Kubernetes API                                                     │
└──────────┬─────────────────────────────────────────────────────────▲──────────────┘
           │ metrics every 2 s + pod state, events, deploys, limits    │ restart / scale / rollback
           ▼                                                           │
┌──────────────────────── ETERNALAI (namespace "eternalai") ──────────┴──────────────┐
│ COLLECT → DETECT → PREDICT → ROOT CAUSE → IDENTIFY → CHOOSE FIX → RULEBOOK → ACT   │
│             │         │          │            │            │                  │    │
│      IsolationForest Trend/Holt  Map+ranker   Classifier   KB + outcomes  VERIFY   │
│      + z-score                   (trained)    (trained)                     │      │
│                                                   │ unknown → human + LLM   │      │
│                         LEARN ◄──── incident + fix + result ────────────────┘      │
│ Dashboard (internal, SSO) · small DB (incidents, KB, outcomes) · model files        │
└──────────┬─────────────────────────────────────────────────────────────────────────┘
           ▼
     People: Slack / Telegram / PagerDuty (report + [Approve] button) · optional LLM

 Offline, before deployment: Dataset A → classifier + root-cause ranker; Dataset B + C → fix ranking
```

### 7.2 Component roles

| Component | Role | Analogy |
|---|---|---|
| Prometheus | 8 health signals over time | Eyes |
| Kubernetes API | Limits, deploys, restarts, pod state, service map; executes fixes | Context + hands |
| Detect / Predict | Learn each service's normal on site; flag and forecast | Instinct |
| Root-cause ranker + fault classifier | Trained on dataset A | Brain |
| Knowledge base + outcome ranking | Every fix, its risk, measured success | Experience |
| Rulebook | Company policy: auto vs approval, protected services | Manager's rules |
| LLM (optional) | Report writing; suggestions for unknown faults (never acts) | Writer |

### 7.3 Two timelines

- **Offline (before deployment):** train classifier and ranker on dataset A; choose the "unknown" confidence threshold on validation data; build fix ranking from B + C. Model files ship inside the EternalAI container image.
- **Online (at the company):** Detect and Predict learn that company's normal during the first days (Watch mode). Trained models run **only when an incident opens**. Every solved incident is appended to A/B/C; models are retrained periodically (e.g. weekly).

---

## 8. The loop, step by step: input → processing → output

| # | Step | Input | Processing | Output (example) |
|---|---|---|---|---|
| 1 | Collect | Prometheus + Kubernetes API | Pull 8 signals per service; pod states, restarts, deploy events, limits | Health table: `payments: p95 95 ms, err 0%, mem 246/300 MB, up` |
| 2 | Learn normal (background) | Healthy history | Rolling mean/std per signal per service; Isolation Forest fit on normal data | `payments mem normal = 120 ± 10 MB` |
| 3 | Detect | Health table + normal | z-score and Isolation Forest with streak rules | `payments ABNORMAL: memory 12.6σ above normal` |
| 4 | Predict | Last 8 readings + limits | Linear fit (R² ≥ 0.8) → time to limit; Holt → traffic forecast | `payments memory full in ~29 s` |
| 5 | Root cause | Abnormal services + service map + deploys | Deepest abnormal service; v2: trained ranker probability per service | `root = payments; impacted = orders, web` |
| 6 | Make features | Root service history + normal + limits + pod state + deploy flag + map | Relative features (ratios, z, shares, slopes, graph) | One feature row |
| 7 | Identify | Feature row | Trained classifier → class probabilities; threshold → known/unknown | `memory_leak 0.92` or `UNKNOWN` |
| 8 | Choose fix | Fault type | KB lookup + outcome ranking | `1. restart_with_helper (low) 2. scale_out 3. raise_limit` |
| 9 | Rulebook | Fix + risk + mode + service policy | Policy evaluation | `Autopilot + low risk → RUN NOW` / `[Approve]` |
| 10 | Act | Approved fix | Kubernetes API call | `rolling restart of payments, no downtime` |
| 11 | Verify | Health table 16 s later (root + callers) | Healthy? else wait 30 s grace → retry next fix once → escalate | `RESOLVED` |
| 12 | Learn | Whole incident | Append rows to A (features+label), C (fix+result); B if new fault solved | New data rows |
| 13 | Explain | Timeline + KB entry | Template or LLM | `"Payments was leaking memory and would have crashed in ~29 s. Restarted, no downtime."` |

**Input to the AI models is not one snapshot.** It is the last 1–3 minutes of the health table, made relative to each service's own normal, plus Kubernetes context (limits, recent deploys, restarts, service map).

---

## 9. AI and ML components in detail

### 9.1 Detect — z-score + Isolation Forest (unsupervised, learns on site, no dataset needed)

**Z-score (one signal at a time):** `z = (value − mean_normal) / max(std_normal, floor)`. Abnormal if `z > 3` **and** the absolute gap exceeds a minimum, for 3 checks in a row. Baseline only absorbs values that looked normal (a problem never becomes the new normal).

**Isolation Forest (all signals together):** trained on the service's healthy data with features `[p95, err, cpu, mem_ratio, sat]`, 100 trees. Output per service per tick = **one anomaly score** (`decision_function`): `> 0` normal, `< 0` abnormal. Rule: `< −0.08` for 5 checks. It catches **combinations** that look fine one by one.

**Turning the score into words (never show raw scores to users):**
1. Rank each signal's z-score to find which signals caused it.
2. Map score to level: normal (green) / watching (yellow, 0 to −0.08) / abnormal (red, < −0.08 × 5).
3. Message: *"Payments memory 246/300 MB, far above its normal 120 MB, rising 1.85 MB/s, full in ~29 s."*
4. If no single signal explains it → *"unusual combination"* → **no automatic action**, ask a human.

### 9.2 Predict — trend + Holt (time-series, fits live)

- **Time to limit (memory, disk, connections):** linear regression on last 8 points; `slope`, `R²`; trust only if `R² ≥ 0.8`; `eta = (limit − now) / slope`. Act when `eta ≤ fix_time + margin` (memory 75 s, disk 60 s).
- **Traffic (overload):** Holt double exponential smoothing
  `level = 0.4·x + 0.6·(level + trend)`; `trend = 0.15·(level − level_prev) + 0.85·trend`; `forecast(16 s) = level + 8·trend`. If forecast > capacity → scale out **before** saturation; scale back in when calm.

### 9.3 Root cause — service map rule + trained ranker

- **Rule (v1, kept as baseline and safety net):** among abnormal services, blame those whose downstream dependencies are all healthy (deepest abnormal). Recent deploy (≤ 300 s) is a prime suspect.
- **Ranker (v2, trained on dataset A, target `is_root`):** gradient-boosted classifier scores each service's probability of being the root using its relative features + graph features (`is_deepest_anomalous`, `n_callees_anomalous`, `n_callers_anomalous`, `depth_from_entry`, `callers_client_lat_max_ratio`). Rank services in the incident by probability. Report top-1 and top-3.
- **Service map source in Kubernetes:** OpenTelemetry service-graph connector or service-mesh telemetry if present; otherwise derive from traces, or from a config/annotation (`eternalai.io/depends-on`).

### 9.4 Identify — trained fault classifier (supervised, needs dataset A)

- **Model:** gradient boosting (scikit-learn `HistGradientBoostingClassifier`; handles missing values; XGBoost/LightGBM optional). Many small decision trees learn rules like *"memory slope > 0.1/min and traffic ratio < 1.5 → memory_leak"* from data — **we do not write these rules by hand**.
- **Input:** one feature row for the root service (see §10.4).
- **Output:** probability per fault type, e.g. `memory_leak 0.92, overload 0.04, oom_kill 0.02 …`.
- **Unknown faults:** if the top probability is below a threshold (e.g. 0.6, chosen on **validation** data, never on test) → `UNKNOWN`: no automatic fix; evidence to a human; LLM searches the knowledge base for similar cases and **suggests** options; once solved, the case becomes new training data.
- **Two strong root candidates at once** → treat as unknown (a single-fault model can be fooled by two faults).
- **Second target:** `category` (6 groups) as a coarser, more robust fallback.

### 9.5 Choose fix — knowledge base + outcome ranking (dataset B + C)

- KB lists every fix per fault with risk (low/medium/high), automation (automatic/needs approval), when to use, when not to use, verify condition, time to effect, permanent human fix.
- Ranking from measured outcomes (C): **no crash > recovered > fewer failed requests > faster recovery**. Where not yet measured, the KB prior (SRE practice) is used and flagged as such.
- Measured so far (vs no action): memory_leak → restart_with_helper; disk_filling → disk_cleanup; app_error → restart_with_helper; slow_service → restart_with_helper; bad_deploy → rollback_deploy; overload → scale_out; crash → restart_in_place; cpu_runaway → close call (no action 0% vs restart 0.7% failed; restart only if users affected).

### 9.6 LLM (optional) — report writer and advisor

- Providers in v1: Gemini (`gemini-2.5-flash`) or Groq (`llama-3.3-70b-versatile`); fallback: built-in template writer.
- Uses retrieval over the knowledge base (RAG) for unknown faults; must cite the KB rows used.
- **Never executes actions.** Redact secrets/PII before sending anything outside the cluster; can be disabled or self-hosted.

### 9.7 Learn

Every incident writes: feature row + confirmed fault (→ A), fix + outcome metrics (→ C), and for solved unknown faults a new KB entry (→ B). Periodic retraining replaces model files.

---

## 10. The dataset

### 10.1 Why

Detect and Predict need no dataset (they learn each system's normal live). **Identify** and **Choose fix** need labelled examples. No public dataset contains *issue + consequence + all fixes + best fix* together, so we built a three-part dataset.

### 10.2 The three parts

| Part | Answers | Content | Size (v1) |
|---|---|---|---|
| **A. Labelled telemetry** | What does each fault look like in the numbers? | One row per (incident, service): relative features + `fault_type` + `is_root` + `role` (root/victim/healthy) | 295 incidents, 7,880 service rows (+735 RCAEval cases indexed, telemetry to add) |
| **B. Knowledge base** | What is it, what does it cause, all fixes, best fix? | Per fault: symptoms, distinguishing clues, consequences, causes, all fixes with risk + automation, optimal fix, permanent fix, sources | 17 fault types, 72 fault×fix options, 23 fix actions |
| **C. Fix outcomes** | Which fix actually works? | Our measured runs: fault, fix, recovered, crashed, failed %, times; vs no action | 59 runs over 8 faults; 71-row experiment matrix of pairs still to run |
| D. Detector tests | Is the anomaly detector good on real servers? | NAB AWS CloudWatch series, SMD server machines (anomaly yes/no only) | 20 series, 327 events |

### 10.3 Sources

| Source | Used for |
|---|---|
| Nezha (FSE 2023) | 101 injected faults on Online Boutique (10 services) & Train Ticket (46): CPU, memory, network, latency, error logs, call graph from traces |
| Amazon PetShop (CLeaR 2024) | 68 faults on a 41-component AWS app: latency, requests, availability, call graph |
| RCAEval | Index of 735 cases (OB, Sock Shop, TT): cpu, mem, disk, delay, loss, socket, code faults F1–F5 |
| Our prototype benchmark | 59 runs, 8 faults, Autopilot vs Watch-only |
| IBM ITBench | 24 Kubernetes faults with consequence, alerts and every fix command |
| Microsoft AIOpsLab | 31 problem types mapped to our taxonomy |
| awesome-prometheus-alerts | 374 alert rules mapped to fault types |
| danluu/post-mortems, k8s.af | 267 real outages keyword-matched to fault types (verify by hand) |

### 10.4 Features (all relative — work on any company's system)

| Feature | Meaning |
|---|---|
| `lat_ratio`, `cpu_ratio`, `rps_ratio`, `mem_ratio`, `net_rx_ratio`, `net_tx_ratio` | value during incident ÷ service's own normal |
| `lat_z`, `cpu_z`, `mem_z`, `rps_z`, `client_lat_z` | movement in normal standard deviations |
| `cpu_share_max`, `mem_share_max`, `disk_share_max` | peak use as share of limit |
| `lat_slope_rel`, `cpu_slope_rel`, `mem_slope_share_per_min`, `disk_slope_share_per_min` | trend per minute |
| `err_base`, `err_fault`, `err_delta` | error rate normal, during, difference |
| `up_frac` | share of time up |
| `sys_lat_ratio`, `sys_err_delta` | entry-service (front door) view |
| `client_lat_ratio`, `callers_client_lat_max_ratio` | callers see slow calls while service is fine → network clue |
| `anomaly_score`, `n_callees`, `n_callers`, `n_callees_anomalous`, `n_callers_anomalous`, `is_deepest_anomalous`, `depth_from_entry` | graph / root-cause features |
| `disk_io_ratio`, `socket_ratio` | filled from RCAEval |
| Labels | `fault_type`, `category`, `is_root`, `role`, `source_fault`, `mapping_quality` |

**Do not use as features:** `sampling_s`, `n_fault_points`, `source`, `system`, `case_id` (they identify the dataset → shortcut). Log features (`log_err_*`) exist only for Nezha → excluded by default (leakage).

### 10.5 Label mapping rules

Original labels are kept in `source_fault`; `mapping_quality` = exact / close / none. Labels with no match are **not forced** (e.g. RCAEval "disk" = disk I/O stress ≠ disk space → `disk_io_pressure`, excluded). Nezha `cpu_contention`/`cpu_consumed` → `cpu_runaway`; `exception` → `app_error`; `return` → `logic_bug` (out of scope, unknown-path test). PetShop delay → `slow_service`, error → `app_error`, DynamoDB flood → `db_slowdown`. RCAEval mem → `memory_leak` (close), socket → `resource_exhaustion` (close), delay → `network_delay`, loss → `packet_loss`.

### 10.6 Quality audit of v1 (fault-classifier table: 277 incidents, 11 classes)

| Check | Result |
|---|---|
| Balance score (normalised entropy) | 84.7% |
| Imbalance ratio | 11.2 : 1 (normal 24.2%, db_slowdown 2.2%) |
| Classes with < 30 real cases | 55% (6 of 11) |
| Planned types with zero real cases | 38% (crash_loop, oom_kill, packet_loss, dns_failure, bad_config, resource_exhaustion) |
| Empty cells in features | 38.3% |
| Source guessed from empty-cell pattern | 100% (shortcut risk) |
| Fault types from only one source | 64%; label↔source Cramér's V 72% |
| Train score / never-seen-system score | 100% / 33% macro-F1 (12–59%) → **overfitting gap 67 points** |

### 10.7 Balanced dataset v2 — method

1. **Split first, real data only for checking.** Split by whole incident. Test = all Train Ticket incidents (53, never-seen system). Validation = 20% of remaining incidents per class (43). Unknown-fault test = 18 logic-bug incidents.
2. **Oversample training classes to 50 rows each** (no real rows removed):
   - **Severity augmentation:** same fault 0.75–1.25× as strong (deviation from normal scaled).
   - **Jitter:** ±5% noise.
   - **SMOTE:** new point between two real incidents of the same fault from the same source.
   Every synthetic row has `is_synthetic=True` and `parent_case_id` (stays on the same split side as its parent).
3. **Neutral filling:** unmeasured signal = "no change from normal" (ratio 1, change 0). Empty cells 38.3% → 0%. **The same rule must be applied at run time.**
4. **Negative sampling for the root-cause set:** root + victims + a few healthy services per incident → root share 4.0% → 9.5%.
5. **Coarser label** `category` (6 groups).

**Result:** balance 100%, imbalance 1:1, empty-cell shortcut removed, val/test 100% real. Accuracy on the never-seen system did **not** materially change (58% → 54–65% over 6 seeds, mean 58%). Synthetic rows only re-mix existing information — **more real incidents are what will raise accuracy.**

### 10.8 Dataset files

| File | Use |
|---|---|
| `train_balanced.csv` | Train fault classifier (550 rows: 181 real + 369 synthetic) |
| `val_real.csv` | Tune settings, choose unknown threshold (43 real) |
| `test_unseen_system_real.csv` | **Final score to report** (53 real, Train Ticket) |
| `test_unknown_fault_real.csv` | Model should be unsure (18 logic bugs) |
| `root_cause_train_sampled.csv` | Train root-cause ranker |
| `train_real_only.csv`, `root_cause_all_rows.csv`, `v2_class_summary.csv` | Comparison / full rows / counts |
| v1 workbook: `B_fault_knowledge_base.csv`, `B_fix_options.csv`, `B_fix_catalog.csv`, `B_itbench_fault_library.csv`, `B_alert_rules.csv`, `B_real_incidents.csv`, `C_fix_outcomes_runs.csv`, `C_fix_ranking.csv`, `C_experiment_matrix.csv`, `A_rcaeval_case_index.csv` | Knowledge base, outcomes, RCAEval index |
| Scripts: `build_part_a.py`, `build_part_b.py`, `build_part_c_d.py`, `add_rcaeval.py` (index / download / convert), `build_v2.py`, `eval_v2.py`, `train_baseline.py` | Rebuild everything |

### 10.9 Dataset rules (non-negotiable)

- Never put synthetic rows in validation or test. Never split by random rows — split by incident and by system.
- Never choose thresholds, seeds or models by looking at the test score.
- Report macro-F1 + confusion matrix on the never-seen system as the headline number.
- Every external KB row keeps its source link; a team member must review AI-assisted rows (`reviewed_by_team`).

---

## 11. Tech stack

| Layer | v1 (prototype) | v2 (build target) |
|---|---|---|
| Language | Python 3.12 | Python 3.12 |
| Web/API | Starlette + Uvicorn | same |
| ML | scikit-learn (IsolationForest), NumPy | + HistGradientBoosting (or XGBoost/LightGBM), joblib model files, pandas |
| Metrics | Prometheus + PromQL (DNS service discovery) or direct `/metrics` scrape; psutil | kube-prometheus-stack (Prometheus Operator, cAdvisor, kube-state-metrics); optional Grafana Beyla (eBPF) / OpenTelemetry for latency without code changes |
| Service map | static `TOPOLOGY` dict | OpenTelemetry service-graph connector / traces / annotations |
| Actions | Docker Engine API (unix socket) / local processes | **Kubernetes Python client** (`kubernetes`), in-cluster service account |
| Orchestration | Docker Compose | Kubernetes (kind/minikube for demo; EKS/GKE/AKS in industry) |
| Packaging | Dockerfiles | + **Helm chart**, RBAC YAML |
| Storage | in-memory + JSONL/CSV | SQLite/PostgreSQL (incidents, KB, outcomes) on a PVC |
| Fault injection | own `/chaos` endpoints | + **Chaos Mesh** (Pod/Stress/Network/DNS/IO chaos) or LitmusChaos |
| Demo apps | 4-service shop | + **Online Boutique** (Google microservices-demo), Sock Shop |
| Dashboard | HTML/CSS/JS, SVG charts | same + incident detail, approvals, fault confidence |
| Notifications | Telegram | + Slack (interactive approve button) |
| LLM | Gemini / Groq / template fallback | same, RAG over KB, optional self-hosted |

---

## 12. How it runs in a real company (deployment)

EternalAI is **not** a browser extension or a terminal tool; it is a **background service installed inside the company's cluster**, running 24/7 next to their apps.

### 12.1 Install

```bash
helm install eternalai eternalai/eternalai --namespace eternalai --create-namespace \
  --set prometheus.url=http://prometheus-operated.monitoring:9090 \
  --set mode=watch \
  --set namespaces="{shop,payments}"
```

Components created in namespace `eternalai`: `brain` Deployment (loop + API + dashboard, 1–2 replicas with leader election), Service + Ingress (internal, behind SSO), PVC for the small database, ServiceAccount + Role/RoleBinding per allowed namespace, ConfigMap (rulebook/policy), Secret (Slack/Telegram tokens, optional LLM key). Model files are baked into the image.

If the company has no Prometheus, the chart can install kube-prometheus-stack.

**Without Kubernetes** (plain servers/Docker): one EternalAI box connects to each host's Docker API (through a restricted socket proxy) and a metrics agent — exactly how the v1 prototype works.

### 12.2 Data stays inside

All telemetry and decisions stay in the company's network. Outbound only: notifications, and the optional LLM (short incident summary with secrets removed, or a self-hosted model).

### 12.3 Adoption stages (how trust is built)

| Stage | Duration | Behaviour |
|---|---|---|
| Watch | 1–2 weeks | Read-only; learns normal; shows what it *would* do |
| Shadow | ~2 weeks | Compare suggestions with what engineers did → accuracy on *their* system |
| Ask | ongoing | Every action needs one-tap approval |
| Autopilot (partial) | ongoing | Low-risk fixes automatic on chosen services; payments/DB always ask |

### 12.4 What the Kubernetes API provides

**Information:** deployments/pods/replica counts, pod status (Running/CrashLoopBackOff/Pending/OOMKilled), restart counts, events, rollout history (ReplicaSets with `deployment.kubernetes.io/revision`), resource limits, services/labels, node conditions (DiskPressure), HPA state, pod logs, watch streams.
**Controls:** rolling restart (patch template annotation `kubectl.kubernetes.io/restartedAt`), scale (`deployments/scale`), delete pod, rollback (re-apply previous ReplicaSet's pod template — there is no "undo" endpoint in apps/v1), pause rollout, change limits, patch HPA, cordon node, create Job.
**Not provided:** time-series health numbers → that is Prometheus.

### 12.5 Example PromQL for the 8 signals in Kubernetes

```promql
# p95 latency (app histogram or Beyla/OTel http_server_request_duration_seconds)
histogram_quantile(0.95, sum by (le, service) (rate(http_server_request_duration_seconds_bucket[30s])))
# error rate
sum by (service) (rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[30s]))
  / sum by (service) (rate(http_server_request_duration_seconds_count[30s]))
# traffic
sum by (service) (rate(http_server_request_duration_seconds_count[30s]))
# CPU share of limit
sum by (pod) (rate(container_cpu_usage_seconds_total{container!=""}[30s]))
  / sum by (pod) (kube_pod_container_resource_limits{resource="cpu"})
# memory share of limit
sum by (pod) (container_memory_working_set_bytes{container!=""})
  / sum by (pod) (kube_pod_container_resource_limits{resource="memory"})
# restarts and OOM kills
increase(kube_pod_container_status_restarts_total[5m])
kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}
# readiness (up/down)
kube_pod_status_ready{condition="true"}
```

---

## 13. Permissions (RBAC) and security

Principle: **least privilege**, permissions grow with the mode, namespaced (not cluster-wide), reviewed by the company's security team before install.

### 13.1 Watch mode (read-only)

- Prometheus read-only token.
- `get/list/watch` on pods, deployments, replicasets, services, events, HPA; `get` on nodes; optional `pods/log`.
- Cloud read-only (CloudWatch, RDS describe) via cloud-issued identity (EKS IRSA / GKE Workload Identity), no long-lived keys.

### 13.2 Ask / Autopilot (act), only in allowed namespaces

| Action | Permission | Risk |
|---|---|---|
| Rolling restart | `patch` deployments | low |
| Scale | `update/patch` `deployments/scale` | low |
| Restart crashed pod | `delete` pods | low |
| Disk cleanup | app cleanup endpoint or a cleanup Job (avoid `pods/exec`) | low |
| Rollback | `patch` deployments (previous template), `get/list` replicasets | high → approval |
| Revert config | `patch` configmaps | high → approval |

### 13.3 Never granted

Secrets, deleting deployments/namespaces/PVCs/databases, any database write, RBAC changes, `kube-system`.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role                      # one per allowed namespace
metadata: { name: eternalai-act, namespace: shop }
rules:
- apiGroups: ["apps"]
  resources: ["deployments", "deployments/scale", "replicasets"]
  verbs: ["get", "list", "watch", "patch", "update"]
- apiGroups: [""]
  resources: ["pods", "events", "services"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["delete"]
# no secrets, no delete on deployments, no RBAC
```

Other: Slack/Telegram/PagerDuty bot token in a Secret; dashboard behind company SSO (OIDC) with an approver list; Docker hosts only through a socket proxy allowing list/restart.

---

## 14. Safety controls

- **Kill switch:** one toggle returns everything to Watch mode.
- **Limits:** max 2 attempts per incident; 40 s cooldown per service; cap on actions per hour; one service at a time; replica min/max.
- **Protected services:** payments and databases always need approval, in any mode.
- **High-risk actions** (rollback, config revert, limit changes, DB anything) always need approval.
- **Verify then escalate:** never keep trying random fixes; crash loops are never "fixed" by more restarts.
- **Unknown faults:** never auto-fixed.
- **Audit trail:** every action logged (what, why, evidence, who approved, result); Kubernetes audit logs show the `eternalai` service account.
- **No secrets read; data stays in-cluster; LLM optional and redacted.**

---

## 15. Interfaces: dashboard, API, notifications, configuration

### 15.1 Dashboard (port 8080)

Live service map (green/yellow/red), per-service charts, incident list with timeline (Predicted → Detected → Diagnosed → Waiting/Fixing → Verified/Escalated), approval buttons, mode switch, "Crash it"/chaos buttons for demos, stats (detection-to-fix, fix-to-verified).

### 15.2 Brain API (v1)

| Route | Purpose |
|---|---|
| `GET /` | Dashboard |
| `GET /api/state` | Services, incidents, actions, approvals, stats |
| `POST /api/mode` | `{"mode": "watch" | "ask" | "autopilot"}` |
| `POST /api/approvals/{id}` | `{"approve": true|false}` |
| `POST /api/chaos/{service}/{kind}` | Inject a demo fault |
| `POST /api/deploy/{service}` | Deploy demo version (v2 is buggy) |
| `POST /api/traffic` | Change load generator rate |
| `GET /api/registry` | Discovered services/replicas |

v2 additions to plan: `GET /api/incidents/{id}` (features, class probabilities, root ranking, chosen fix, KB rows), `GET /api/kb/{fault_type}`, `POST /api/feedback/{incident}` (human confirms/corrects fault → training data), `GET /healthz`.

### 15.3 Notifications

Example:
> 🔴 **Payments: memory leak (92% sure)**
> Memory 246 of 300 MB, far above its normal 120 MB, rising 1.85 MB/s — full in ~29 s.
> Root cause: payments (orders, web affected). Action: restart with helper copy (no downtime).
> ✅ Verified healthy at 15:03:12. Permanent fix: developer should check the leak.

### 15.4 Configuration (env vars, v1)

`RUNTIME` (docker|local), `METRICS_SOURCE`, `PROMETHEUS_URL`, `LOADGEN_URL`, `DOCKER_SOCKET`, `BRAIN_PORT`, `TICK_SECONDS`, `MAX_REPLICAS`, `COOLDOWN_SECONDS`, `VERIFY_AFTER_SECONDS`, `MAX_ATTEMPTS`, `MODE`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
v2 adds: `RUNTIME=kubernetes`, `NAMESPACES`, `POLICY_FILE` (rulebook YAML), `MODEL_DIR`, `UNKNOWN_THRESHOLD`, `SLACK_*`, `DB_URL`.

### 15.5 Rulebook (policy YAML, v2)

```yaml
mode: ask                     # watch | ask | autopilot
protected_services: [payments, postgres]   # always ask
auto_allowed_risks: [low]     # in autopilot
max_actions_per_hour: 10
namespaces: [shop]
fault_overrides:
  cpu_runaway: { act_only_if_user_impact: true }
  db_slowdown: { action: escalate }
```

---

## 16. Build plan for the hackathon (v2)

Priority order. Each task has an acceptance check.

| # | Task | Acceptance check |
|---|---|---|
| 1 | **Kubernetes driver** (`drivers/k8s.py`): list services/pods, rolling restart, scale, delete pod, rollback to previous ReplicaSet, cleanup via app endpoint/Job | Same driver interface as `DockerDriver`; works on kind/minikube with Online Boutique |
| 2 | **Kubernetes metrics source**: PromQL for 8 signals (§12.5) + kube-state-metrics (restarts, OOMKilled, limits, readiness) + deploy events | Health table identical in shape to v1 |
| 3 | **Service map discovery**: from traces/OTel or annotations; fallback static config | `TOPOLOGY` built automatically for Online Boutique |
| 4 | **Feature builder** (`features.py`): live incident → feature row exactly matching dataset schema (§10.4), incl. neutral filling | Unit test: bench incident reproduces dataset row |
| 5 | **Fault classifier + root-cause ranker**: train on `train_balanced.csv` / `root_cause_train_sampled.csv`; save with joblib; load in brain; confidence threshold from `val_real.csv` | Report macro-F1 + confusion matrix on `test_unseen_system_real.csv`; unknown flag rate on `test_unknown_fault_real.csv` |
| 6 | **Replace runbook** with classifier + KB lookup + outcome ranking; keep rule-based root cause as fallback | Incident shows probabilities, chosen fix, backups, KB link |
| 7 | **Rulebook YAML** + protected services + approvals (Slack/Telegram button) | Payments action always waits for approval |
| 8 | **Learn store** (SQLite/Postgres): append incidents in dataset A/C format; `POST /api/feedback` | New rows appear after each incident |
| 9 | **Chaos Mesh experiments** for missing faults: crash_loop, oom_kill, dns_failure, bad_config, packet_loss, resource_exhaustion; and more runs for weak classes | ≥ 5 runs per fault, logged as new real data |
| 10 | **Part C experiments**: run each candidate fix on each fault (≥ 4–5 runs) | `C_experiment_matrix.csv` status → measured |
| 11 | **Helm chart + RBAC** | `helm install` on a fresh cluster works in Watch mode |
| 12 | **Dashboard updates**: confidence, root ranking, unknown state, approvals | Demo-ready |
| 13 | **Add RCAEval** telemetry via `add_rcaeval.py download/convert` and retrain | Never-seen-system score reported before/after |

---

## 17. Proposed v2 repository layout

```
eternalai/
├── CLAUDE.md                     # this file
├── brain/
│   ├── main.py  engine.py  config.py  policy.py
│   ├── sources/ prometheus.py  k8s_state.py  direct.py
│   ├── drivers/ docker.py  local.py  k8s.py
│   ├── detect.py  predict.py  diagnose.py
│   ├── features.py               # live incident → dataset-format row
│   ├── models/ classifier.py  ranker.py  artifacts/*.joblib
│   ├── kb/ knowledge_base.csv  fix_options.csv  fix_catalog.csv  ranking.py
│   ├── learn.py  store.py  explain.py  notify.py
│   └── static/
├── data/                         # dataset v1 + v2 CSVs (read-only inputs)
├── training/ build_*.py  train_classifier.py  train_ranker.py  evaluate.py
├── chaos/ chaos-mesh/*.yaml      # one experiment per fault type
├── deploy/ helm/eternalai/  rbac/  kind-cluster.yaml  online-boutique/
├── services/                     # v1 demo shop (kept for local demo)
└── bench/                        # benchmark runner + results
```

---

## 18. Evaluation: how we measure and report results

| Step | Metric | How | Compare against |
|---|---|---|---|
| Identify | Macro-F1 + confusion matrix | Train on other systems, **test on never-seen system** (Train Ticket) | Majority class; v1 rules |
| Unknown | % unknown flagged; % known wrongly flagged | Logic-bug set; leave-one-fault-out | Always "known" |
| Root cause | Top-1 / top-3 accuracy | All systems | Random; "highest anomaly score" |
| Detect | Event-level precision/recall, detection delay | Injection runs, each fault counted once, **no point-adjust** | Fixed thresholds (CPU > 90%) |
| False alarms | Alarms per day | 24 h healthy run | Fixed thresholds |
| Predict | Lead time; crashes prevented | Leak/disk with vs without EternalAI | Watch-only |
| Choose fix | Success rate, recovery time, failed requests | ≥ 5 runs per fault×fix | "Always restart"; no action |

Rules: split by run and system; ≥ 5 repeats; report median and range; publish the confusion matrix; choose thresholds on validation only.

**Current baselines:** fault classifier 96% macro-F1 on mixed systems (inflated by source shortcuts) vs **33% (12–59%) on never-seen systems**; root cause top-3 0.75–0.80 on Online Boutique (10 services), 0.18–0.43 on 42–46-service systems; unknown-fault AUROC ≈ 0.66.

---

## 19. Demo script

1. Dashboard: healthy service map, Autopilot on, Online Boutique (or demo shop) under load.
2. Inject memory leak on `payments` → Predicted ("full in ~X s") → classifier `memory_leak 9x%` → restart with helper copy → verified; no crash. Show Watch-only run crashing for contrast.
3. Inject bad deploy → `bad_deploy` → rollback **waits for approval** → approve on Telegram/Slack → verified.
4. Traffic surge → forecast → scale out ahead → scale back in.
5. Kill a pod / crash → restart in seconds.
6. Inject an unseen pattern → **UNKNOWN** → no action, evidence + LLM suggestions to a human.
7. Show the incident report, audit trail and the new training row created by Learn.
8. Close with the honest numbers slide (§20).

---

## 20. Known limitations and honest numbers

- Prototype acts through Docker on one machine; Kubernetes driver, Helm chart and RBAC are the v2 build.
- Fault classifier generalises poorly to unseen systems today (33% average macro-F1; 58% on Train Ticket) because 64% of fault types come from a single source and 6 planned types have no real data. Balancing did not fix this; **more real data will** (RCAEval + own Chaos Mesh injections on 2 systems).
- Part C measures one fix per fault vs no action; other fault×fix pairs are still to be run.
- Lab-injected faults are cleaner than real incidents; claim "tested on injected faults".
- Knowledge base was drafted with AI help and keyword-matched incidents; each row must be verified by the team.
- Runaway CPU: restart cost 0.7% failed requests vs 0% with no action → act only if users are affected.
- Two faults at once can confuse a single-fault classifier → treated as unknown.

---

## 21. How to answer common questions

| Question | Answer |
|---|---|
| "Is it just a wrapper around Kubernetes?" | Kubernetes/Prometheus are eyes and hands that every tool uses; the decisions (which service, which fault, which fix, is it safe, did it work) are our trained models and logic. Turn the LLM off and it still works. |
| "What if someone deletes the database?" | Every read/write fails → errors on all DB users while their CPU/memory are normal → root cause = DB → one alert with evidence + restore-from-backup playbook. We never auto-restore or touch the DB; we cut time-to-understand from ~30 min to ~30 s. |
| "What if the pipeline fails?" | Before release, no customer impact, out of scope. If a broken build is deployed it becomes a bad deploy → caught in seconds → rollback with approval. |
| "What is an error in production?" | Any runtime backend fault visible in the 8 health signals — our 15 fault types. |
| "Where is AI used?" | Detect (Isolation Forest), Predict (trend/Holt), Root cause (trained ranker), Identify (trained classifier), Choose fix (outcome ranking), Explain (optional LLM). |
| "When is the dataset used?" | Before deployment to train the classifier/ranker and build fix ranking; live when an incident opens; after incidents to grow and retrain. |
| "What permissions does it need?" | Read: metrics, pods, deployments, events. Act: patch/scale deployments, delete pods in allowed namespaces. Never: secrets, deletes, DB writes, RBAC. |
| "What if the AI is wrong?" | Kill switch, approvals for risky actions, protected services, max 2 attempts, verify-then-escalate, audit log. |

---

## 22. Rules for anyone writing code on this project

1. Keep the **driver interface** identical across Docker, local and Kubernetes (`replicas()`, `restart()`, `scale_to()`, `rollback()`, `cleanup()`).
2. The **feature builder must produce exactly the dataset schema** (§10.4) with the same neutral-filling rule; add a unit test.
3. **Never** let the LLM call actions. Never auto-execute high-risk fixes or anything on protected services.
4. Never read Kubernetes Secrets; never write to databases.
5. Every action goes through the rulebook, is logged, and is verified (service + upstream callers).
6. All thresholds/settings in config, overridable by env vars; defaults as in §6.3.
7. Training/evaluation: split by incident and system; no synthetic data in val/test; thresholds from validation only; report never-seen-system scores.
8. Plain-English user messages; never show raw anomaly scores.
9. Python 3.12, type hints where useful, small modules, no heavy frameworks; scikit-learn + joblib for models.
10. Keep the v1 demo working (`docker compose up --build`, dashboard on `:8080`).

---

## 23. Glossary

| Term | Meaning |
|---|---|
| Microservice | Small backend service doing one job (payments, orders) |
| Root cause | The service that started the problem; others are victims |
| p95 latency | 95% of requests are faster than this |
| Saturation | How full a service's capacity/queue is |
| z-score | How many standard deviations a value is from normal |
| Isolation Forest | Unsupervised ML that flags points easy to isolate (unusual) |
| Holt's method | Forecast using level + trend |
| Macro-F1 | Average F1 over classes (each fault type counts equally) |
| SMOTE | Creates synthetic samples between two real samples of the same class |
| Helm | Kubernetes package installer |
| RBAC | Kubernetes permissions (Role, RoleBinding) |
| Chaos Mesh | Tool to inject faults into Kubernetes on purpose |
| Watch / Ask / Autopilot | Read-only / approve every fix / auto low-risk fixes |

---

## 24. Sources

- RCAEval — https://github.com/phamquiluan/RCAEval (arXiv 2412.17015)
- Nezha — https://github.com/IntelligentDDS/Nezha
- PetShop — https://github.com/amazon-science/petshop-root-cause-analysis
- IBM ITBench — https://github.com/IBM/ITBench-Scenarios
- Microsoft AIOpsLab — https://github.com/microsoft/AIOpsLab
- awesome-prometheus-alerts — https://github.com/samber/awesome-prometheus-alerts
- danluu/post-mortems — https://github.com/danluu/post-mortems · Kubernetes Failure Stories — https://k8s.af
- NAB — https://github.com/numenta/NAB · SMD (OmniAnomaly) — https://github.com/NetManAIOps/OmniAnomaly
- Online Boutique — https://github.com/GoogleCloudPlatform/microservices-demo · Sock Shop — https://github.com/microservices-demo/microservices-demo · Train Ticket — https://github.com/FudanSELab/train-ticket
- Chaos Mesh — https://github.com/chaos-mesh/chaos-mesh · LitmusChaos — https://github.com/litmuschaos/litmus
- Kubernetes docs — https://kubernetes.io/docs · Google SRE book — https://sre.google/sre-book
- Wu & Keogh, *Current Time Series Anomaly Detection Benchmarks are Flawed* — https://arxiv.org/abs/2009.13807
- Kim et al., *Towards a Rigorous Evaluation of Time-series Anomaly Detection* — https://arxiv.org/abs/2109.05257
