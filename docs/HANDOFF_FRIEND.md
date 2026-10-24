# EternalAI: handoff for the Codex session (Phase 2, Phase 4 partial, Phase 6)

This file is everything a second AI coding session (OpenAI Codex CLI, in a second terminal **on this same machine**)
needs to build three work packages in parallel with the main session (Claude Code) without the two disturbing each
other. Read it once, fully, before typing a command. Codex also reads `AGENTS.md` at the repository root automatically;
that file points here. The prompts to paste into Codex are in section 11.

| | Main session (Claude Code) | Codex session |
|---|---|---|
| Folder | `D:\eAI\eAI-release` | `D:\eAI\eAI-codex` (a git worktree of the same repository) |
| Branch | `plan-complete` | `friend/phase2-k8s` first; later `friend/phase6-telegram` if time remains |
| Python venv | `D:\eAI\eAI-workspace\eAI\.venv` | its own: `D:\eAI\eAI-codex\.venv` |
| `.env` | `D:\eAI\eAI-release\.env` | its own copy: `D:\eAI\eAI-codex\.env` (made by the owner by hand) |
| Docker, ports, RAM, image names | **shared**: one stack at a time, by the lock in section 1.5 | **shared** |

- Repository: https://github.com/py007105/eAI (GitHub is not needed for this handoff: both folders share one local `.git`).
- Base for your work: the local branch `plan-complete`.
- Code freeze: **2026-10-23 20:00 IST**. Hackathon: 24-25 October 2026.
- The owner decides every merge. The main session merges your finished branch into `plan-complete`; you never do.

---

## 0. What you are building, in one screen

EternalAI watches a 4-service demo shop (web -> orders -> payments, inventory) on Docker Compose, detects faults from
Prometheus metrics every 2 s, finds the root-cause service, classifies the fault with a trained model, asks a YAML
rulebook whether a fix may run, runs it through Docker, and verifies recovery. An independent evaluator injects faults
and scores the brain without the brain seeing the answer.

The plan (`docs/ETERNALAI_PLAN.md` once added; the original is outside the repo) wants more. The Codex session owns
three work packages:

| Package | Plan phase | Branch | Size | Needs from the owner |
|---|---|---|---|---|
| **B. Telegram notifications + approvals** | Phase 6 | `friend/phase6-telegram` | medium | a Telegram bot token and chat id, typed by the owner into `D:\eAI\eAI-codex\.env` (never committed, never shown to Codex) |
| **A. Kubernetes (minimal)** | Phase 2 | `friend/phase2-k8s` | largest | kind + helm downloads (allowed: pinned versions, checksums verified); the Docker lock for long periods (kind needs the RAM the Compose stack uses) |
| **C. Knowledge base + outcome-ranked fixes + dataset-A classifier** | Phase 4 (partial) | `friend/phase4-kb` | medium | the dataset files' folder path |

Order (owner's decision, 2026-10-21): **A (Kubernetes) first.** B (Telegram) only if time remains before the freeze; it may
also be built during the hackathon. **C is done by the main session**, not by Codex (the dataset is at `D:\eAI\plan_dataset\`,
read-only).

The main session meanwhile works on: Phase 3 (prediction live), the engine-core parts of Phase 4 (close root
candidates -> abstain, forest-only anomaly -> no auto action), Phase 5 light (learn store + feedback), Phase 7
(benchmark re-runs). **Do not do those.**

---

## 1. Ground rules (read twice)

### 1.1 Git rules: the ones that cause real damage

Both folders share **one** `.git` directory. A wrong git command in `D:\eAI\eAI-codex` can change branches, tags or
history that the main session depends on. Therefore:

1. **Work only inside `D:\eAI\eAI-codex`.** Never `cd` into, edit, or run git in `D:\eAI\eAI-release` or
   `D:\eAI\eAI-workspace\eAI`.
2. **Commit only to your own `friend/...` branch.** Never commit to, reset, or merge into `plan-complete`, `main`,
   `release-candidate`, `v2-dev`, `hardening` (git refuses to check out `plan-complete` here anyway, because the main
   session has it checked out; do not work around that with `--force` or `--ignore-other-worktrees`).
3. **Never push** unless the owner explicitly says "push friend/<branch>". Never force-push anything.
4. **Never rewrite history:** no `git rebase`, no `git reset --hard` (except the one recovery case in 3.7), no
   `git commit --amend` on a commit the main session may already have merged, no `git filter-branch`.
5. **Never create, move or delete tags.** Tags (`benchmark-system-v1/-v2`, `models-v1/-v2`, `v1.0.0-rc.*`,
   `demo-stable-*`) mark measured systems.
6. **Never delete branches** and never run `git worktree remove`, `git worktree prune`, `git gc --prune=now`,
   `git clean -fdx`, `git stash clear`, `git branch -D`.
7. **One branch per package.** Do not mix Telegram and Kubernetes changes.
8. **Small commits, one logical change each,** message format in 3.3.
9. **Never commit:** `.env`, tokens, keys, kubeconfig files, `data/runs/`, `data/raw/`, `runtime/`,
   `results/demo-export/`, `.venv/`, `__pycache__/`, `*.tgz` chart packages, large binaries, dataset files.
   Run `git status` before every `git add`; add files **by name**, never `git add .` or `git add -A`.
10. **Shared files** (section 5): `eternalai/engine.py`, `eternalai/policy.py`, `eternalai/rulebook.py`,
    `eternalai/api.py`, `eternalai/config.py`, `docker-compose.yml`, `dashboard/app.py`, `evaluator/*`,
    `models/artifacts/*`, `results/*`, `docs/results/*` (except files your scripts generate), `tests/test_autopilot_path.py`,
    `tests/test_policy.py`, `docs/PLAN_GAP_CLOSURE.md`. Touch them only as section 5 allows, each in its own small commit
    whose message starts with `shared:`.

### 1.2 Secrets

- Codex must never read, print, log, copy or commit: `.env` (in any folder), `ETERNALAI_APPROVAL_TOKEN`, `CHAOS_TOKEN`,
  `GEMINI_API_KEY`, `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, kubeconfig contents, cluster tokens. If a step needs a secret,
  Codex asks the owner to set an environment variable or to edit `.env` by hand.
- The Telegram bot token is inside every Bot API URL (`https://api.telegram.org/bot<TOKEN>/...`) and httpx exceptions
  contain the URL. **Never log a Telegram exception message;** log only `type(e).__name__`. Pattern:
  `tests/test_dashboard_fixes.py`.
- Everything that leaves the machine (Telegram text) goes through `eternalai/redact.py: redact()` first.

### 1.3 Honesty rules for results

- **Never invent a number.** Every number in docs comes from a script that ran and wrote a results file.
- If a measurement disagrees with the plan, write the measured number and say it disagrees.
- If something does not work, say so with the error; do not hide it or fake it.
- **No fakes or mocks in the running system or the demo.** Fakes only inside `tests/`.
- Every feature runs **live, end to end** on the real stack (Compose; kind for package A), checked by a committed
  script. The final report says, per item, "verified live" or "verified in tests only".

### 1.4 Code rules (from the plan §22 and this repo)

- Python 3.12+ (containers use 3.12; the suite runs on 3.14 here), type hints where useful, small modules.
- The LLM never calls actions. Never auto-execute high-risk fixes or anything on protected services; every action
  goes through `PolicyEngine.evaluate` (the rulebook) and the executor's audit log.
- Never read Kubernetes Secrets; never write to databases.
- Plain-English user messages; never show raw anomaly scores to users.
- Every new module gets tests. The full suite passes after every commit:
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` (2 `live` tests are deselected by default).

### 1.5 Sharing this machine with the main session (Docker, ports, RAM, images)

Both sessions use the **same Docker daemon**, the same Compose project name (`eai`, fixed in `docker-compose.yml`),
the same host ports and the same image names (`eai/eternalai:v2`, `eai/web:v1`, ...). Running `docker compose up`
from `D:\eAI\eAI-codex` **replaces the main session's containers with your code.** So:

1. **The Docker schedule and lock: `D:\eAI\STACK_LOCK.md`.** The file starts with the agreed Docker schedule until the freeze;
   kind work happens only in the windows marked for Codex. The **last line** is the lock. Before any `docker compose up/build/stop/start/restart`, any
   `docker run`, any `kind create/delete`, read the file.
   - If it says `FREE`, write: `HELD by codex | <what> | since <YYYY-MM-DD HH:MM IST> | expected until <HH:MM> | images built from <branch>@<hash>`.
   - If it says `HELD by main`, **do not touch Docker**; tell the owner and wait.
   - When done: stop what you started (`docker compose -p eai stop`, `kind delete cluster --name eai`) and write
     `FREE | last: codex | images now built from <branch>@<hash>`.
   - Read-only commands (`docker ps`, `docker images`, `docker compose ps`) need no lock.
2. **Images:** if you build `eai/*` images, they now contain your branch's code. Record that in the lock file, as
   above. Whoever takes the lock next rebuilds before trusting the images. For kind, build the brain under a separate
   tag, `eai/eternalai:k8s-dev`, never `:v2`.
3. **Ports in use by the Compose stack:** 8000, 8050, 8080, 8200, 9090, 16686. For kind port-forwards use 18000-18099.
4. **RAM:** about 15.7 GB in total, often only 2-6 GB free.
   - Never run kind and the Compose stack at the same time.
   - Check free RAM before starting anything heavy (PowerShell:
     `(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB`). Kind + Online Boutique needs about 6 GB free.
5. **Runtime files** (`runtime/audit.jsonl`, evidence) are written relative to the folder you run from; yours stay
   in `D:\eAI\eAI-codex\runtime\` (git-ignored). The brain in a container writes to the `eternalai-runtime` volume:
   never delete volumes (`down -v`, `docker volume rm`, `docker system prune --volumes`).
6. **Unit tests need no lock:** they never touch Docker.

---

## 2. One-time setup

### 2.1 Create the Codex worktree (the owner runs this once, in a normal PowerShell, not inside either AI session)

```powershell
cd D:\eAI\eAI-release
git worktree add D:\eAI\eAI-codex -b friend/phase2-k8s plan-complete
git -C D:\eAI\eAI-codex log --oneline -3          # the top commit must equal plan-complete's
if (-not (Test-Path D:\eAI\STACK_LOCK.md)) { "FREE | last: none" | Set-Content -Encoding utf8 D:\eAI\STACK_LOCK.md }
```
Then the owner, by hand (not through any AI): copy `D:\eAI\eAI-release\.env` to `D:\eAI\eAI-codex\.env` (and, only when
package B starts, add `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` there, section 7.2). Check that git ignores it:
`git -C D:\eAI\eAI-codex check-ignore .env` must print `.env`.

### 2.2 Python environment (Codex may run this)

```powershell
cd D:\eAI\eAI-codex
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```
Expected (verified 2026-10-21 on a clean clone): `462 passed, 2 deselected` or more. **If anything fails before you
changed anything, stop and tell the owner** with the failing test names.

New packages (e.g. `kubernetes` for package A) are installed **only into `D:\eAI\eAI-codex\.venv`**, pinned in the
requirements file in the same commit. Never install into `D:\eAI\eAI-workspace\eAI\.venv` (the main session's).

### 2.3 Start Codex

```powershell
cd D:\eAI\eAI-codex
codex
```
- Use an approval mode in which Codex **asks before** running commands that touch the network, Docker or anything
  outside the workspace (in Codex: `/approvals`).
- Do not use any "full access" or "bypass approvals and sandbox" mode for this project.
- If your Codex version supports the flags, `codex --sandbox workspace-write --ask-for-approval on-request` does this
  at start.
- Paste prompt 11.1 first.

### 2.4 Check that the shared stack works (needs the Docker lock)

Only when `D:\eAI\STACK_LOCK.md` says FREE and you have written your HELD line:
```powershell
docker compose --profile releases build
docker compose up -d
.\.venv\Scripts\python.exe scripts\stock_gate.py --restock --force
.\.venv\Scripts\python.exe scripts\preflight.py
docker compose -p eai stop
```
Then write FREE in the lock file. All ports are bound to 127.0.0.1. **Never** `down -v`.

---

## 3. Git workflow, step by step (all inside `D:\eAI\eAI-codex`)

### 3.1 Start of each session

```powershell
git branch --show-current          # must be your friend/... branch
git status                         # must be clean; if not, commit your own work first
git merge plan-complete            # bring in the main session's new work (local branch; a merge, never a rebase)
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```
If the merge reports conflicts, see 3.6. No `git fetch` is needed: `plan-complete` is the same local branch the main
session commits to.

### 3.2 While working

```powershell
git status
git diff                           # read the diff before every commit
git add path\to\file1 path\to\file2   # by name
git commit                         # message format below
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider   # after EVERY commit
```

### 3.3 Commit messages

```
<Area>: <what changed, imperative, <= 72 chars>

<why; what it fixes or adds; any measured number with its results file>
<for shared files: exactly which lines and why they had to change>
```
Examples: `Telegram: send incident messages with approve/reject buttons`,
`shared: engine.py calls the notifier after each status change (3 lines)`.

### 3.4 Handing a finished package back (instead of a pull request)

When the package meets its definition of done (section 9):
1. `git merge plan-complete`, run the full suite and the package's live check again.
2. Write the hand-back note from the template in section 10 to `docs/handback/<branch-name>.md` and commit it on your
   branch.
3. Tell the owner: "package <X> is ready on friend/<branch> at <hash>". The owner tells the main session, which reviews,
   merges into `plan-complete`, re-runs the suite and its live checks, and reports back.
4. Start the next package on a **new** branch from the current `plan-complete`:
   ```powershell
   git status                                      # clean
   git switch -c friend/phase2-k8s plan-complete
   ```
   Never reuse a finished branch for new work.

Pushing to GitHub: only when the owner says "push friend/<branch>" (e.g. as a backup):
`git push -u origin friend/<branch>`. Never push any other branch, never with `--force`.

### 3.5 If the main session asks for changes after review

Commit the fixes on the same `friend/...` branch (new commits; no amend, no rebase) and tell the owner the new hash.

### 3.6 Merge conflicts

- They happen when both sessions changed the same lines. Open each conflicted file and keep **both** intents.
- In shared files, prefer the main session's version and re-apply your few lines on top.
- After resolving: `git add <files>`, `git commit` (the merge commit), run the full suite.
- If unsure: `git merge --abort` restores the state before the merge. Then ask the owner.

### 3.7 Mistakes and how to undo them safely

| Mistake | Safe fix |
|---|---|
| Committed on the wrong `friend/...` branch, nothing merged yet | `git branch friend/<right-name>` (keeps the commit), then tell the owner; do not reset anything until the owner agrees |
| Ran a git command in `D:\eAI\eAI-release` by mistake | **Stop.** Tell the owner exactly what ran. Do not try to undo it yourself. |
| Pushed anything by accident | **Stop. Never force-push.** Tell the owner the branch and hash. |
| Committed a secret | Tell the owner. The secret is rotated (new bot token via @BotFather, new random tokens) whether or not it was pushed. The owner decides how to remove the commit. |
| Committed a large or wrong file (no secret), not yet handed back | `git rm --cached <file>`, add a `.gitignore` entry if right, commit again (new commit; no amend) |
| Tests fail after merging `plan-complete` | Find out whether your change or the main session's broke it; if the main session's, report the test names; do not "fix" their code on your branch |
| Detached HEAD | `git switch friend/<name>` |
| Want to throw away your own uncommitted edits in one file | `git restore <file>` |
| Changed the shared stack's containers without the lock | Stop them (`docker compose -p eai stop`), write the lock file honestly, tell the owner |

Never run: `git push --force*`, `git rebase`, `git reset --hard`, `git tag ...` (create/delete), `git push --delete`,
`git branch -D`, `git clean -fdx`, `git worktree remove/prune`, `git gc --prune=now`, `git filter-branch`,
`docker compose down -v`, `docker volume rm`, `docker system prune`.

---

## 4. The codebase you need to know

| Path | What it is |
|---|---|
| `eternalai/engine.py` | the loop: `tick()` -> `_observe()` -> detect -> open incident -> `_diagnose()` -> `_propose()` -> policy -> `_run_async()` -> `_act_and_verify()`; `approve()` / `reject()`; incidents in `self.incidents` (class `Incident`) |
| `eternalai/policy.py` | `PolicyEngine.evaluate(runbook, service, fault=, user_impact=)` -> `Decision(verdict, reason, risk)`; verdicts `execute`, `needs_approval`, `blocked`, `observe_only` |
| `eternalai/rulebook.py`, `eternalai/rulebooks/*.yaml` | the policy file (plan §15.5): mode, auto_allowed_risks, protected_services, max_actions_per_hour, cooldown, risks, fault_overrides, namespaces |
| `eternalai/executor.py` | `Executor.run(runbook_id, service, actor, evidence_ids, reason)`: the 4 Docker runbooks, each audited to `runtime/audit.jsonl` |
| `eternalai/collector.py` | `Prom.signals(service)` -> DataFrame of 12 signals (`Q` dict = the PromQL); `DockerView` = container state |
| `eternalai/classify.py` | `CAUSE_RUNBOOKS` (fixed cause -> runbook table), classifier wrapper, abstain logic |
| `eternalai/api.py` | FastAPI on :8000. `_auth()` = the token check used by every state-changing endpoint |
| `eternalai/redact.py` | `redact(text)`: remove secrets/PII before anything leaves the machine |
| `eternalai/config.py` | `SERVICES`, `TOPOLOGY` (static call graph), `CALLERS`, URLs, timings |
| `dashboard/` | Dash UI on :8050 |
| `evaluator/` | independent fault injector + scorer on :8200 (owns the ground truth) |
| `scripts/live_check_phase1.py` | **the pattern to copy for your live checks**: throwaway tokens passed via environment, real stack, PASS/FAIL table written to `docs/results/` |
| `tests/test_autopilot_path.py` | `make_engine(...)` builds a real Engine with fake telemetry/executor; reuse it in your unit tests |
| `docs/PLAN_GAP_CLOSURE.md` | every plan requirement with status; your rows are listed in sections 6-8 here |

Brain API endpoints you will use: `GET /status`, `GET /incidents`, `GET /approvals`,
`POST /approvals/{id}/approve` and `/reject` (header `X-Approval-Token`, body `{"approver": "..."}`),
`POST /mode`, `POST /killswitch`, `GET /audit`. Starting a fault: evaluator `POST /runs` with the token header
(`scripts/harness_auth.py`).

Default rulebook (`eternalai/rulebooks/default.yaml`): autopilot runs only low-risk actions; rollback is high (always
approval); `payments` is protected (always approval); 10 actions per hour; cooldown 40 s.

---

## 5. Shared-file contract (to avoid conflicts with the main session)

`docs/PLAN_GAP_CLOSURE.md` is updated only by the main session; list your covered rows in the hand-back note.

| Shared file | Who may change what |
|---|---|
| `eternalai/engine.py` | Package B: one hook call per status change (section 7.4). Package A: replace `Executor()` construction by `make_driver()` (one line) and nothing else. Package C: replace the `CAUSE_RUNBOOKS` lookup by one call (section 8.4). Each in its own `shared:` commit. |
| `eternalai/api.py` | Package B: per-user tokens in `_auth` (section 7.6) and optionally a `/notify/test` endpoint. Package C: `GET /kb/{fault_type}`. |
| `eternalai/config.py` | add new settings at the END of the file only |
| `eternalai/requirements.txt` | add pinned lines only (`kubernetes==<version>`) |
| `docker-compose.yml` | Package B: pass `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` to the `eternalai` service as `${VAR:-}`. Nothing else. |
| `eternalai/rulebook.py` | Package B may add one optional top-level key `approvers` (section 7.6) with validation and tests. |
| everything else listed in 1.1 rule 9 | not yours |

---

## 6. Package A: Kubernetes, minimal (Phase 2) — branch `friend/phase2-k8s`

Plan references: §7, §11, §12, §13, §16 tasks 1-3 and 11, §22 rule 1.
Gap rows: A1, A2, A3, A4, A5, A7, R4, H1, H2, H8(Prometheus token), P14, L2, L3.
In scope: Driver interface; KubernetesDriver (restart, scale, rollback, delete pod); Kubernetes metrics source;
annotation-based service map with static fallback; Helm chart + namespaced RBAC; one scripted kind end-to-end check
with Online Boutique. **Roadmap, not now:** leader election, kube-prometheus-stack install, Sock Shop, Train Ticket live
(not feasible on this hardware), Chaos Mesh.

RAM rule from the owner: **one app at a time; the Compose stack is stopped while kind runs.** On this shared machine that
means holding the Docker lock (section 1.5) for the whole kind session and telling the owner, because the main
session cannot run its stack meanwhile. Batch kind work into few long sessions.

### 6.1 Target layout (new files)

```
eternalai/drivers/__init__.py      make_driver() chooses by RUNTIME=docker|kubernetes (default docker)
eternalai/drivers/base.py          Driver protocol + NotSupported error
eternalai/drivers/docker.py        DockerDriver: wraps the existing Executor UNCHANGED
eternalai/drivers/k8s.py           KubernetesDriver (official `kubernetes` Python client)
eternalai/sources/k8s_metrics.py   PromQL for Kubernetes (cAdvisor + kube-state-metrics) -> same columns as Prom.signals
eternalai/sources/service_map.py   topology from Deployment annotations; static config.TOPOLOGY fallback
deploy/kind/kind-cluster.yaml      1 control-plane + 1 worker (or single node), pinned node image
deploy/kind/VERSIONS.md            exact versions + SHA256 of kind, helm, node image, charts, Online Boutique release
deploy/helm/eternalai/             Chart.yaml, values.yaml, templates/{deployment,service,serviceaccount,role,rolebinding,configmap-rulebook,secret}.yaml
deploy/online-boutique/annotate.sh adds eternalai.io/depends-on annotations (and a .ps1 twin)
scripts/kind_e2e.py                the scripted end-to-end check (section 6.8)
tests/test_drivers.py, tests/test_k8s_driver.py, tests/test_k8s_metrics.py, tests/test_service_map.py, tests/test_helm_chart.py
docs/KUBERNETES.md                 how to run it, what works, what does not
```

### 6.2 Tools (pinned, checksums verified)

- Use a kind and helm release that is at least two weeks old. Download from the official GitHub releases page.
- Verify the SHA256 against the checksum file published **on the same release page**:
  - Windows: `Get-FileHash .\kind.exe -Algorithm SHA256`;
  - macOS / Linux: `shasum -a 256 kind`.
- Put the binaries in `D:\eAI\tools\` (outside the repository; never commit them). Ask the owner before each download.
- Write the version, URL and hash into `deploy/kind/VERSIONS.md`. Never pipe a remote script into a shell.
- `kubectl` usually comes with Docker Desktop.
- Pin the Online Boutique release tag (use its `release/kubernetes-manifests.yaml`) and the Prometheus chart version in the same file.

### 6.3 Driver interface (plan §22 rule 1)

```python
class Driver(Protocol):
    runtime: str                                   # "docker" | "kubernetes"
    audit: list[dict]
    def run(self, runbook_id: str, service: str, actor: str, evidence_ids=None, reason: str = "") -> dict: ...
    def log_verification(self, incident_id, runbook_id, service, outcome, success_rate) -> dict: ...
    def replicas(self, service: str) -> int: ...
    def restart(self, service: str) -> dict: ...
    def scale_to(self, service: str, n: int) -> dict: ...
    def rollback(self, service: str) -> dict: ...
    def cleanup(self, service: str) -> dict: ...
    def delete_pod(self, service: str) -> dict: ...
```
- `DockerDriver` delegates `run`/`log_verification`/`audit` to the existing `Executor` (do **not** change
  `executor.py` behaviour; the Docker demo must behave exactly as before). `scale_to`, `delete_pod` raise
  `NotSupported` (audited). `replicas` returns 1.
- Runbook mapping for Kubernetes `run()`:
  - `restart_service` -> rolling restart: patch the Deployment's pod template annotation
    `kubectl.kubernetes.io/restartedAt` to an ISO timestamp.
  - `recreate_container` -> `delete_pod` (the ReplicaSet replaces it).
  - `rollback_release` -> find the ReplicaSet with the previous `deployment.kubernetes.io/revision`, patch the
    Deployment template to that ReplicaSet's template (there is no "undo" endpoint in apps/v1; plan §12.4).
  - `clear_temp_path` -> `NotSupported` in this minimal version (plan wants an app endpoint or a Job; roadmap).
  - `scale_out` is not a runbook in the rulebook yet: expose `scale_to()` on the driver and test it, but do not add a
    new runbook to `KNOWN_RUNBOOKS` (that is a policy change for the owner).
- **D7, "not supported" with a test:** pause rollout, change limits, patch HPA, cordon node, create Job. Add
  `UNSUPPORTED = (...)` and a test that each raises `NotSupported` and is audited.
- **Safety inside the driver:**
  - refuse any namespace not in the rulebook's `namespaces` (P14);
  - never call any Secret API;
  - never delete Deployments, Namespaces or PVCs;
  - every call writes an audit record (what, why, who, result), exactly like the Executor.

### 6.4 RBAC (plan §13, least privilege, namespaced)

`templates/role.yaml`, one Role per allowed namespace, exactly the plan's rules:
```yaml
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
```
In watch mode (`values.mode=watch`), bind a read-only Role instead (get/list/watch only). No ClusterRole, no Secrets,
no `pods/exec`, nothing in `kube-system`. The e2e check verifies this with `kubectl auth can-i --as=system:serviceaccount:<ns>:eternalai`.

### 6.5 Helm chart

- `values.yaml`:
  - `image` (repository, tag);
  - `mode` (watch | ask | autopilot; default **watch**);
  - `namespaces` (list);
  - `prometheus.url`;
  - `rulebook` (inline YAML rendered into a ConfigMap and mounted; `ETERNALAI_POLICY_FILE` points at it);
  - `approvalToken.existingSecret` (the chart never renders a token value from values);
  - `resources`.
- Deployment: 1 replica (leader election is roadmap), `RUNTIME=kubernetes`, the ServiceAccount, liveness `/health`.
- Service: ClusterIP only (no Ingress in the minimal version).
- Acceptance: `helm lint` passes; `helm template` renders; `helm install` on a fresh kind cluster gives a Ready brain
  in watch mode.
- Test `tests/test_helm_chart.py` runs `helm template` if `helm` is on PATH (skip otherwise) and asserts:
  - no Secret data from values;
  - Role verbs equal the plan's;
  - no ClusterRole.

### 6.6 Kubernetes metrics source

Produce the **same column names** as `collector.Q` so the rest of the engine is unchanged.
Starting PromQL (plan §12.5), per Deployment `{s}` in namespace `{ns}`:

| column | PromQL |
|---|---|
| cpu_cores | `sum(rate(container_cpu_usage_seconds_total{namespace="{ns}",pod=~"{s}-.*",container!=""}[30s]))` |
| mem_bytes | `sum(container_memory_working_set_bytes{namespace="{ns}",pod=~"{s}-.*",container!=""})` |
| mem_limit_bytes | `sum(kube_pod_container_resource_limits{namespace="{ns}",pod=~"{s}-.*",resource="memory"})` |
| up | `min(kube_pod_status_ready{namespace="{ns}",pod=~"{s}-.*",condition="true"})` |
| restarts_3m | `sum(increase(kube_pod_container_status_restarts_total{namespace="{ns}",pod=~"{s}-.*"}[3m]))` |
| deploys_3m | `changes(kube_deployment_status_observed_generation{namespace="{ns}",deployment="{s}"}[3m])` |

- `req_rate`, `err_rate`, `p95_s`, `dep_fail_rate`, `error_log_rate`, `scratch_bytes`: Online Boutique exposes no HTTP
  metrics by default. Leave them **missing (NaN)** and say so in `docs/KUBERNETES.md`; the detector handles NaN.
  Do not fill them with zeros.
- Select with `METRICS_SOURCE=kubernetes`.
- OOM kills: `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}`, exposed in the state reader.
- Optional: send a Prometheus bearer token when `PROMETHEUS_TOKEN` is set (H8).
- Unit tests: use `httpx.MockTransport`, as in `tests/test_collector.py`.

**Honest limit to document:** the trained detectors, classifier and ranker were trained on the demo shop's services.
On Online Boutique there are no trained detectors for its services, so the engine uses its explicit fallbacks
(`fit_baseline` live baseline, `rule_diagnose`, `deepest_anomalous`), shown in `/status` as `fallbacks_in_use`.
That is expected for this phase; write it down, do not hide it.

### 6.7 Service map discovery

- Read Deployments in the allowed namespaces.
- `eternalai.io/depends-on: "a,b,c"` annotation -> edges.
- Services without the annotation have no callees.
- If discovery fails or finds nothing, fall back to `config.TOPOLOGY` and set a flag shown in `/status`.
- Online Boutique call graph to annotate (from its architecture diagram; verify against the pinned release):
  - frontend -> adservice, cartservice, checkoutservice, currencyservice, productcatalogservice,
    recommendationservice, shippingservice
  - checkoutservice -> cartservice, currencyservice, emailservice, paymentservice, productcatalogservice, shippingservice
  - recommendationservice -> productcatalogservice
  - cartservice -> redis-cart
- `deploy/online-boutique/annotate.sh` applies these with `kubectl annotate deployment ... --overwrite`.
- Test: a fake Deployment list gives the expected topology; an empty list falls back.

**Engine wiring (shared commit, minimal):**
- `config.SERVICES` / `TOPOLOGY` are module constants used at import time.
- Add `config.load_topology()` at the end of `config.py`. It returns the discovered map when `RUNTIME=kubernetes`,
  else the static one.
- Call it once at Engine start.
- If this needs more than a few lines in `engine.py`, stop and describe the change in the hand-back note instead of making it.

### 6.8 End-to-end check: `scripts/kind_e2e.py`

Pattern: `scripts/live_check_phase1.py` (PASS/FAIL table, throwaway token in the environment, results file
`docs/results/kind_e2e.md` + `results/live-checks/kind_e2e.json`). Steps:
1. Check `D:\eAI\STACK_LOCK.md` is FREE, write `HELD by codex | kind e2e | ...`, confirm the Compose stack is stopped
   (`docker compose -p eai ps` shows nothing running) and about 6 GB RAM are free; otherwise abort with a clear message.
2. `kind create cluster --config deploy/kind/kind-cluster.yaml --name eai`.
3. Install Prometheus (pinned chart, includes kube-state-metrics, scrapes cAdvisor) into `monitoring`.
4. Install Online Boutique (pinned manifests) into `shop`; annotate; wait for all Deployments Available.
5. Build the brain image as `eai/eternalai:k8s-dev` (never `:v2`, which the Compose demo uses) and `kind load docker-image` it.
6. Create the approval-token Secret from a throwaway value generated by the script (never printed).
7. `helm install eternalai deploy/helm/eternalai -n eternalai --create-namespace` with `mode=watch`,
   `namespaces={shop}`. Check: brain Ready, `/status` answers (via `kubectl port-forward` on a port in 18000-18099).
8. RBAC matrix via `kubectl auth can-i`: allowed verbs yes; secrets / delete deployments / kube-system / pods/exec no.
9. Discovered topology equals the annotated graph.
10. Metrics frame from in-cluster Prometheus: cpu/mem/up/restarts present for every Deployment.
11. Driver actions, each audited:
    - rolling restart of `currencyservice` (pods replaced, Available again);
    - `scale_to(recommendationservice, 2)` then back to 1;
    - delete one `adservice` pod (replaced);
    - rollback (step 12).
12. Full loop:
    - switch to `ask` via `POST /mode`;
    - break `productcatalogservice` with a bad image (`kubectl set image ... server=<image>:does-not-exist`);
    - the brain detects it (readiness down) and proposes `rollback_release`, which is **high** and waits;
    - check nothing was executed before approval;
    - approve via `POST /approvals/{id}/approve`;
    - the driver rolls back;
    - Deployment Available; verification recorded.
13. Teardown: `helm uninstall`, `kind delete cluster --name eai`, write `FREE | last: codex | ...` in the lock file.
    Leave the Compose stack stopped; the main session restarts it.

Verification on Kubernetes: `verify.py` probes the shop's `/api/checkout`, which Online Boutique does not have.
- Add a generic probe in a **new** module, `eternalai/verify_k8s.py`. It checks that the target Deployment and all its
  callers (from the service map) have every replica Ready, and that the frontend `GET /` returns 200 through a
  port-forward (port 18000-18099) or the in-cluster Service. It runs for the same observation window.
- Engine wiring: one `shared:` line choosing the verifier by `RUNTIME`.
- This also covers plan row L5 ("verify root and callers") for Kubernetes.

### 6.9 Definition of done (package A)

- [ ] `pytest` passes, new tests for every new module
- [ ] Docker demo unchanged: `scripts\preflight.py` passes on Compose after your changes (under the Docker lock)
- [ ] `scripts/kind_e2e.py` passes end to end on this machine; results file committed; lock released
- [ ] `docs/KUBERNETES.md` explains install, what works, what does not (missing HTTP metrics, fallbacks, no leader election)
- [ ] `deploy/kind/VERSIONS.md` has every version and SHA256
- [ ] hand-back note `docs/handback/friend-phase2-k8s.md` committed (template in section 10)

---

## 7. Package B: Telegram notifications + approvals (Phase 6) — branch `friend/phase6-telegram`

Plan references: §1, §4 (Explain, Rulebook "one tap"), §15.3 (message format), §16 task 7, §19 step 3.
Gap rows: N1, N4, N5, G3, plus H6 deviation (no SSO, per-user approver tokens, owner's decision C5).
Out of scope (documented "not started"): Slack, PagerDuty.

### 7.1 What must work, live

1. When an incident is diagnosed, a Telegram message arrives in the configured chat. Format per plan §15.3: cause +
   confidence (only if `/status.calibration.show_probability` is true), signals in words, root + affected services,
   proposed action and policy verdict, after verification "Verified healthy at HH:MM:SS" or "Escalated".
2. When the policy says `needs_approval`, the message has **Approve** and **Reject** buttons.
3. Tapping a button approves or rejects through **the same checks as the dashboard**: the person must be a known
   approver (per-user token identity), the incident must be pending, the kill switch must be off. A second tap does
   nothing harmful (idempotent: the engine already refuses a non-pending incident).
4. The outcome is edited into the same message (approved by X / rejected by X / expired after 120 s).
5. Nothing secret or personal leaves the machine: all text through `redact()`.

### 7.2 Bot setup (you, by hand)

The owner does these steps by hand; Codex never sees the token.

1. Telegram: talk to @BotFather -> `/newbot` -> copy the token into `D:\eAI\eAI-codex\.env` as `TELEGRAM_BOT_TOKEN=`.
2. Create a private group or use a private chat with the bot; send it one message.
3. Get the chat id: open `https://api.telegram.org/bot<TOKEN>/getUpdates` in **your browser only**, read
   `chat.id`, put it in `D:\eAI\eAI-codex\.env` as `TELEGRAM_CHAT_ID=`. Do not paste the URL into Codex.
4. Your Telegram numeric user id (same page, `from.id`) goes into the approver list (7.6). It is not secret, but keep
   it out of public docs; use the rulebook file on this machine for real ids and a placeholder in the committed file.

### 7.3 New files

```
eternalai/notify/__init__.py     make_notifier() -> TelegramNotifier if both env vars set, else NullNotifier
eternalai/notify/format.py       message text (plain English, plan §15.3), through redact()
eternalai/notify/telegram.py     sendMessage / editMessageText with inline keyboard; getUpdates long-poll thread for button taps
tests/test_notify_format.py, tests/test_telegram.py   (httpx.MockTransport; never real network in unit tests)
scripts/live_check_telegram.py   the live check (7.8)
docs/NOTIFICATIONS.md            setup, security model, what is not built (Slack, PagerDuty)
```

### 7.4 Engine hook (one `shared:` commit)

- Add `self.notifier = make_notifier()` in `Engine.__init__`.
- Call `self.notifier.incident_changed(inc)` at these points, outside the lock where possible. Never let a notifier
  error break the loop: wrap the call in try/except and keep only the exception type in `last_error`.
  - end of `_propose` (status awaiting_approval / executing / escalated);
  - end of `_act_and_verify` (recovered / unresolved);
  - in `_expire_pending` when a proposal expires;
  - in `reject` / `approve`.
- Sending happens on a background thread with a small queue, so a slow Telegram API never delays the loop.
- Tests: reuse `make_engine` from `tests/test_autopilot_path.py` with a fake notifier that records calls; assert one
  notification per status change and that a raising notifier does not break `_propose`.

### 7.5 Button taps without a public URL

- Use `getUpdates` long polling (timeout 25 s) in a daemon thread; no webhook, no inbound port.
- `callback_data`: `"<a|r>:<incident_id>"`, max 64 bytes.
- Accept a callback only if **all** of these hold:
  - `callback_query.message.chat.id == TELEGRAM_CHAT_ID`;
  - `from.id` maps to an approver;
  - the incident exists and is `awaiting_approval`.
- Then call `engine.approve(iid, approver=<approver name>)` or `engine.reject(...)`.
- Always `answerCallbackQuery` with a short result ("approved", "already handled", "not an approver").
- Store the last `update_id` so restarts do not replay old taps.

### 7.6 Per-user approvers (C5: no SSO; documented deviation)

- Rulebook key, validated in `rulebook.py` (shared commit, with tests in `tests/test_rulebook.py`):
  ```yaml
  approvers:
    - name: alice
      token_sha256: "<sha256 hex of alice's personal approval token>"
      telegram_user_id: 123456789
  ```
- `api._auth` (shared commit) keeps the existing single `ETERNALAI_APPROVAL_TOKEN` working **and** accepts any
  approver's personal token, compared as `hmac.compare_digest(sha256(token), token_sha256)`.
- When a personal token is used, the approver name comes from the token, not from the request body (no impersonation).
- Telegram identity: `telegram_user_id` -> that approver's name.
- Never store raw tokens in the rulebook; a script `scripts/hash_token.py` prints only the hash of a token typed at a
  hidden prompt.
- `docs/NOTIFICATIONS.md` must say plainly: this replaces the plan's SSO; anyone who holds an approver's phone or token
  can approve as them.

### 7.7 Compose wiring (one `shared:` commit)

`docker-compose.yml`, `eternalai.environment`: `TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}` and
`TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:-}`. Empty -> NullNotifier, demo unchanged.

### 7.8 Live check `scripts/live_check_telegram.py`

Pattern: `scripts/live_check_phase1.py`. With the real bot (tokens only from the environment / `.env`, never printed),
under the Docker lock (section 1.5), run from `D:\eAI\eAI-codex` so the images contain this branch:
1. Build and start the stack in `ask-first`.
2. Run `crash` on `web` via the evaluator. A message arrives with Approve/Reject. The script prints
   "tap Approve on your phone" and waits up to 100 s; then checks the audit shows `human:<your approver name>` and the
   message was edited to "approved by ... / verified".
3. Run `crash` on `web` again; tap Reject; check escalated, nothing executed.
4. Have a non-approver account tap (optional, or simulate by removing your id and restarting): refused, nothing executed.
5. Turn the kill switch on, run a fault, tap Approve: refused with the kill-switch reason.

Write `docs/results/live_check_telegram.md`. The human taps are part of the check; the script records what happened.
Afterwards stop the stack, write `FREE | last: codex | images now built from friend/phase6-telegram@<hash>`.

### 7.9 Definition of done (package B)

- [ ] unit tests for formatting, redaction of outgoing text, callback validation, per-user tokens, notifier failure isolation
- [ ] live check passed with a real phone tap; results file committed
- [ ] with empty Telegram variables the Compose demo and `scripts/preflight.py` behave exactly as before
- [ ] no token in any log line, test output or committed file (`git grep -n "bot[0-9]\{6,\}:"` finds nothing)
- [ ] `docs/NOTIFICATIONS.md`; Slack and PagerDuty written down as "not started"

---

## 8. Package C: knowledge base, outcome-ranked fixes, dataset-A classifier (Phase 4 partial) — branch `friend/phase4-kb`

Plan references: §9.4, §9.5, §10, §16 tasks 4-6, §18.
Gap rows: X1, X2, X3, T1, T3, C2, C3, C4, C5, C6, C9, C10.
**Blocked until the owner gives you the dataset files**: `EternalAI_training_dataset_v1.xlsx` and the v2 CSVs
(`train_balanced.csv`, `val_real.csv`, `test_unseen_system_real.csv`, `test_unknown_fault_real.csv`,
`root_cause_train_sampled.csv`, `B_*.csv`, `C_*.csv`). RCAEval telemetry is not included; **ask the owner before
downloading anything** (`data/add_rcaeval.py` needs internet).
Not yours (main session): "two close root candidates -> abstain", "forest-only anomaly -> no auto action".

### 8.1 Where the data lives

- The owner gives the dataset folder path. Codex reads the files from there; it never copies them into the repository.
- Ask the owner whether the `B_*` / `C_*` knowledge-base CSVs may be committed (they are small, reviewed text).
  Default until answered: keep them outside git and point to them with `EAI_KB_DIR`.
- Training/test CSVs: never committed. Scripts take `--data-dir`. Record each file's SHA256 in the results file.

### 8.2 Knowledge base loader

- New `eternalai/kb/loader.py`: load `B_fault_knowledge_base.csv`, `B_fix_options.csv`, `B_fix_catalog.csv` (and
  the other B files if present).
- Validate required columns, risk values (low/medium/high), automation values, `reviewed_by_team`, source link
  present for external rows (plan §10.9).
- Rows without `reviewed_by_team == yes` are loaded but flagged; the UI/API must show "unreviewed".
- Plan fault names vs live labels: write an explicit map in `eternalai/kb/labels.py`:
  - `disk_filling` <-> `disk_fill`
  - `crash` <-> `down`
  - `slow_service` <-> `latency_spike`
  - `app_error` <-> `error_spike`
  - `memory_leak`, `bad_deploy` unchanged
  - every unmapped plan type: no live equivalent (state it, do not guess)

### 8.3 Outcome ranking

- New `eternalai/kb/ranking.py`: `ranked_fixes(live_label) -> list[Fix]`, where `Fix` has `runbook_id` (or None if
  not executable here), `name`, `risk`, `automation`, `evidence` (`measured` or `prior`), the outcome numbers, and `kb_row_id`.
- Order (plan §9.5): no crash > recovered > fewer failed requests > faster recovery. Measured outcomes come from
  `C_fix_outcomes_runs.csv` / `C_fix_ranking.csv` and may also come from this repo's benchmark raw files
  (`results/benchmark-v1/benchmark_raw.jsonl`, `results/benchmark-v2/benchmark_v2_raw.jsonl`).
  - Use only real rows.
  - Label each source and its policy file: the v1/v2 benchmark ran under the `benchmark-v2.yaml`-equivalent policy.
  - Where nothing is measured, use the KB prior and set `evidence="prior"`.
- Only fixes whose `runbook_id` is one of the 4 implemented runbooks can be proposed for execution; the others are
  "suggest only".
- If the KB is missing, return the old fixed table (`classify.CAUSE_RUNBOOKS`) with `evidence="fixed table"`.

### 8.4 Engine wiring (one `shared:` commit)

- In `engine._diagnose_compute`, replace `cands = [] if abst else list(CAUSE_RUNBOOKS.get(label, []))` with a call to
  `ranked_runbooks(label)`. It returns executable runbook ids in ranked order and falls back to `CAUSE_RUNBOOKS`.
- Put the full ranked list (with prior/measured flags and KB row ids) into the incident diagnosis record so the
  dashboard and `GET /incidents/{id}` show it (plan task 6: "probabilities, chosen fix, backups, KB link").
- Add `GET /kb/{fault_type}` to `api.py` (read-only, no auth, like `/incidents`).
- `tests/test_autopilot_path.py` must still pass unchanged. If it does not, your ranking changed which runbook is
  proposed: report that in the hand-back note as a behaviour change; do not edit that test.

### 8.5 Dataset-A classifier, reported next to the current one

- New `models/train_dataset_a.py`:
  - HistGradientBoostingClassifier on `train_balanced.csv` (fault_type target);
  - the unknown threshold chosen on `val_real.csv` only (maximise macro-F1 of known-vs-unknown on validation; record
    the rule);
  - category model as the fallback (plan §9.4);
  - leaky columns dropped per plan §10.4 (`sampling_s`, `n_fault_points`, `source`, `system`, `case_id`, `log_err_*`).
- Report, on `test_unseen_system_real.csv` (Train Ticket, never seen in training):
  - macro-F1;
  - per-class recall;
  - confusion matrix;
  - majority-class baseline;
  - unknown flag rate on `test_unknown_fault_real.csv`;
  - known-wrongly-flagged rate.
  Compute the test score once, after every choice is fixed.
- Report the **current live classifier on the same held-out data** only if its features can be computed from the
  dataset columns. They mostly cannot (different schemas). If not, write "not comparable: feature schemas differ
  (list the missing features)". That is an honest result, not a failure.
- Re-measure the plan's numbers (§10.6, §10.7, §18 "current baselines") where these files allow, and list
  plan-number vs measured-number side by side.
- Write `docs/results/dataset_a_classifier.md` from the script, and save the model as
  `models/artifacts/dataset_a_classifier.joblib` + `.json` metadata, the same pattern as `eternalai/artifacts.py`.
- **The brain does not load this model by default.** Do not change `models/artifacts/classifier.*`.
- Leakage test: `tests/test_dataset_a_splits.py` asserts:
  - no `parent_case_id` crosses train/val/test;
  - no synthetic rows in val/test;
  - test system absent from train.

### 8.6 Live check

- Under the Docker lock (section 1.5), from `D:\eAI\eAI-codex`: build and start the Compose stack and run one
  `memory_leak` and one `bad_deploy` evaluator run; stop the stack and release the lock afterwards.
- Check that `GET /incidents/{id}` shows the ranked fixes with measured/prior flags and KB row ids, and that the
  proposed runbook is the top executable fix.
- Script `scripts/live_check_kb.py`; results `docs/results/live_check_kb.md`.

### 8.7 Definition of done (package C)

- [ ] KB loader + validation + tests; ranking + tests; fallback to the fixed table when the KB is absent
- [ ] `tests/test_autopilot_path.py` unchanged and passing (or the behaviour change explained in the hand-back note)
- [ ] dataset-A results file generated by the script, with SHA256 of every input file
- [ ] live check passed; results file committed
- [ ] no dataset file committed unless the owner said yes

---

## 9. Definition of done for every package

1. `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` passes after every commit; the final run is in the hand-back note.
2. The Compose demo still works with your branch (under the Docker lock):
   - `docker compose --profile releases build`;
   - `docker compose up -d`;
   - `scripts\stock_gate.py --restock --force`;
   - `scripts\preflight.py` passes;
   - then stop the stack and release the lock.
3. Your live-check script passed and its results file is committed. The hand-back note says, per item, "verified
   live" or "verified in tests only".
4. Do **not** edit `docs/PLAN_GAP_CLOSURE.md`. Put the plan rows you covered in the hand-back note; the main session
   updates the gap document when it merges.
5. No secrets anywhere:
   - `git log -p plan-complete..HEAD | Select-String -Pattern "(api_key|token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"`
     shows nothing meaningful;
   - `git grep -n "bot[0-9]\{6,\}:"` finds nothing.
6. `git status` is clean on your `friend/...` branch, and the lock file says FREE.

---

## 10. Hand-back note template (`docs/handback/<branch-name>.md`)

```markdown
# Hand-back: <package A / B / C> — branch friend/<...> at <hash>
Merged plan-complete last at: <hash>

## What changed
- <file or module>: <what, one line>
- shared files (each its own `shared:` commit): <file: lines, why>

## Verification
| item | verified live / tests only | evidence |
|---|---|---|
| ... | verified live | docs/results/<file>.md, check `<id>` |

Full test suite: <N> passed, 2 deselected (last line pasted)
Compose demo preflight with this branch: PASS / FAIL (summary)
Images left in Docker: built from <branch>@<hash> (the main session must rebuild before trusting them)

## Measured numbers (if any)
| metric | value | conditions | results file |

## Not done / known limits
- ...

## Plan rows covered
<gap row ids, e.g. N1, N4, N5>
```

---

## 11. Prompts for Codex

Paste one at a time into Codex running in `D:\eAI\eAI-codex`. Replace `<...>`.

### 11.1 First prompt of every Codex session

```
You are working in D:\eAI\eAI-codex, a git worktree of the EternalAI repository, on branch friend/<PACKAGE-BRANCH>.
Another AI session (Claude Code) works at the same time in D:\eAI\eAI-release on branch plan-complete, sharing the same
.git, the same Docker daemon, ports and RAM.
Read AGENTS.md and docs/HANDOFF_FRIEND.md fully, then docs/PLAN_GAP_CLOSURE.md sections A, F and G.
Hard rules for this whole session:
- Work only inside D:\eAI\eAI-codex. Never read, edit or run git in D:\eAI\eAI-release or D:\eAI\eAI-workspace.
- Never read, print or log any .env file or any token, key or kubeconfig. If you need a secret, ask me.
- Commit only to my friend/ branch. Never push. Never rebase, reset --hard, amend, tag, delete branches, or run
  git worktree remove/prune, git clean, git gc.
- Never git add -A or git add . ; show me git status and add files by name.
- Before ANY docker or kind command that starts, stops, builds or changes something, read D:\eAI\STACK_LOCK.md and follow
  section 1.5 of the handoff (write HELD, release with FREE). Never docker compose down -v, never delete volumes.
- Use only D:\eAI\eAI-codex\.venv for Python; install new packages only there and pin them.
- No fakes or mocks outside tests/. No invented numbers: every number comes from a script you ran.
- Run `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` after every commit and show me the last line.
- Changes to shared files (handoff section 5) go in separate small commits starting with "shared:".
First: run `git branch --show-current`, `git status`, `git log --oneline -3`, merge plan-complete if it has new commits
(merge, never rebase), and run the test suite. Report the results. Then summarise my package in 10 lines and list the
first three commits you plan. Wait for my OK before changing anything.
```

### 11.2 Package B (Telegram), build prompt

```
Implement package B from docs/HANDOFF_FRIEND.md section 7, in this order, one commit each, tests with each:
1. eternalai/notify/format.py (plan §15.3 message, redact() on all text) + tests/test_notify_format.py
2. eternalai/notify/telegram.py (sendMessage, editMessageText, inline Approve/Reject, getUpdates long-poll thread,
   callback validation per 7.5; never log URLs or exception messages, only exception type names) + tests with
   httpx.MockTransport, including a test that the bot token never appears in any recorded error or log line
3. eternalai/notify/__init__.py make_notifier() (NullNotifier when the env vars are empty) + tests
4. shared: rulebook `approvers` key with validation + tests in tests/test_rulebook.py
5. shared: api._auth accepts per-user token hashes, approver name taken from the token + tests
6. shared: engine hooks (7.4) with failure isolation + tests using make_engine from tests/test_autopilot_path.py
7. shared: docker-compose.yml passes TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID as ${VAR:-}
8. scripts/hash_token.py and docs/NOTIFICATIONS.md
No Docker needed for steps 1-8 (unit tests only). Stop after each commit, show me the diff summary and the test line.
```

### 11.3 Package B live check prompt

```
Write scripts/live_check_telegram.py following scripts/live_check_phase1.py (read it first) and section 7.8 of the
handoff. Tokens come only from the environment / .env read by docker compose; the script never prints them. It must
wait for my real taps on the phone and record what happened. Then tell me the exact commands to run it. Before I run it:
check D:\eAI\STACK_LOCK.md is FREE, write the HELD line, and remind me the images will be built from this branch.
After it finishes: stop the stack, write FREE with the image note, and commit only the script and its results files.
```

### 11.4 Package A (Kubernetes), build prompt

```
Package A runs on friend/phase2-k8s (the worktree was created on it; if you are on another branch, git status must be clean,
then `git switch friend/phase2-k8s`).
Implement docs/HANDOFF_FRIEND.md section 6, one commit each, tests with each:
1. eternalai/drivers/base.py (Driver protocol, NotSupported, UNSUPPORTED list per D7) + tests
2. eternalai/drivers/docker.py: DockerDriver delegating to the existing Executor with NO behaviour change + tests proving
   identical calls and audit records
3. eternalai/drivers/k8s.py: KubernetesDriver with the official kubernetes client (restart via restartedAt annotation,
   scale_to, delete_pod, rollback to the previous ReplicaSet template, namespace allow-list, audit, no Secret API) + tests
   with fake AppsV1Api/CoreV1Api; pin `kubernetes` in eternalai/requirements.txt (install into .venv only)
4. eternalai/drivers/__init__.py make_driver() by RUNTIME + shared: one-line change in engine.py
5. eternalai/sources/k8s_metrics.py with the PromQL table in 6.6, same columns as collector.Q, NaN for unavailable
   signals + tests with httpx.MockTransport
6. eternalai/sources/service_map.py (annotations, static fallback) + shared: config.load_topology() + tests
7. eternalai/verify_k8s.py (root + callers Ready + frontend GET /) + tests
8. deploy/helm/eternalai chart + RBAC exactly as section 6.4 + tests/test_helm_chart.py (skips without helm)
9. deploy/kind/kind-cluster.yaml, deploy/kind/VERSIONS.md: ask me before each download; verify SHA256 against the
   release's published checksums; put the tools in D:\eAI\tools (not in the repository)
10. scripts/kind_e2e.py per section 6.8 and docs/KUBERNETES.md
After every commit the Docker path must be unchanged: the full suite passes, especially tests/test_autopilot_path.py.
Stop after each commit and show me the diff summary and the test line.
```

### 11.5 Package A live run prompt

```
Before running scripts/kind_e2e.py: read D:\eAI\STACK_LOCK.md (must be FREE), check free RAM (need about 6 GB), confirm
the Compose stack is stopped (`docker compose -p eai ps` shows nothing running), write the HELD line, and show me the
versions in deploy/kind/VERSIONS.md. Build the brain as eai/eternalai:k8s-dev, never :v2. Use port-forwards on
18000-18099 only. Then run the script, show me the PASS/FAIL table, and for every FAIL find the real cause; do not
change the check to make it pass. At the end: kind delete cluster --name eai, write FREE in the lock file.
```

### 11.6 Package C (KB) prompt

```
Start package C on a new branch: git status clean, then `git switch -c friend/phase4-kb plan-complete`.
The dataset files are in <DATA DIR>. Do not copy them into the repository and do not commit them.
Implement docs/HANDOFF_FRIEND.md section 8, one commit each with tests:
1. eternalai/kb/labels.py (explicit plan<->live label map; unmapped types stated)
2. eternalai/kb/loader.py (validation per 8.2) + tests with small fixture CSVs written in the test
3. eternalai/kb/ranking.py (order per 8.3, measured vs prior, fallback to CAUSE_RUNBOOKS) + tests
4. shared: engine uses ranked_runbooks(); api GET /kb/{fault_type}; tests/test_autopilot_path.py must pass unchanged
5. models/train_dataset_a.py + tests/test_dataset_a_splits.py; thresholds from val_real.csv only; test score computed once
6. run it and commit only docs/results/dataset_a_classifier.md and the model artifact + metadata
7. scripts/live_check_kb.py per 8.6 (Docker lock rules apply)
Stop after each commit.
```

### 11.7 Before handing a package back

```
Run: git status; git log --oneline plan-complete..HEAD; git diff --stat plan-complete...HEAD; the full test suite; and
the secret checks from section 9 item 5 of the handoff. Confirm I am on a friend/ branch, that no .env, data, runtime,
kubeconfig or results/demo-export file is committed, and that D:\eAI\STACK_LOCK.md says FREE. Then write
docs/handback/<branch>.md from the template in section 10, filled only from real commits, test output and results files,
commit it, and give me the one-line message for the owner: "package <X> ready on friend/<branch> at <hash>".
Do not push.
```

### 11.8 Getting the main session's new work

```
Run `git merge plan-complete` on my current friend/ branch (merge, NOT rebase). If there are conflicts, show me each
conflicted hunk, propose a resolution that keeps both sides' intent (prefer plan-complete's version in shared files and
re-apply my lines), and wait for my OK before committing the merge. Then run the full test suite.
```

### 11.9 If something goes wrong

```
Stop. Show me git branch --show-current, git status, git log --oneline -5 and the content of D:\eAI\STACK_LOCK.md.
Do not run any command that rewrites history, deletes files, pushes, or changes Docker. Explain what state we are in and
propose the safest fix from section 3.7 of the handoff.
```

---

## 12. Common mistakes (and what to do instead)

| Don't | Do |
|---|---|
| run git or edit files in `D:\eAI\eAI-release` | work only in `D:\eAI\eAI-codex` |
| `docker compose up` without the lock | read and write `D:\eAI\STACK_LOCK.md` first |
| build the kind brain as `eai/eternalai:v2` | use `eai/eternalai:k8s-dev` |
| run kind while the Compose stack runs | one at a time (RAM) |
| `git add -A` and commit a `.env` or `data/runs` | add files by name; `git status` first |
| fix a failing test by changing what it asserts | find why it fails; if the old behaviour was right, fix the code |
| make a live check pass by loosening it | report the FAIL with its cause |
| copy numbers from the plan into docs | run the script; write the measured number |
| edit `engine.py` broadly "while you are there" | one small `shared:` commit with only the agreed lines |
| `docker compose down -v` to "reset" | `docker compose -p eai stop` |
| retrain or overwrite `models/artifacts/classifier.*` | new artifacts get new names |
| log a Telegram/Kubernetes exception message | log `type(e).__name__` only |
| `git rebase plan-complete` | `git merge plan-complete` |
| pip install into the main session's venv | only `D:\eAI\eAI-codex\.venv` |

---

## 13. Coordination and timeline

- The owner relays between the two sessions; the lock file `D:\eAI\STACK_LOCK.md` is the only shared state besides git.
- The main session also follows the lock file: it writes `HELD by main | ...` before using Docker.
- Suggested timeline:
  - package B by 2026-10-22 evening;
  - package A minimal by 2026-10-23 16:00 IST;
  - package C as soon as the dataset path arrives.
- Last hand-back by **2026-10-23 18:00 IST**, two hours before the freeze, so there is time to merge and re-run the
  live checks.
