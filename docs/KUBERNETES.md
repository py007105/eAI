# Kubernetes Package A (minimal)

This package runs the EternalAI brain against one allowed Kubernetes namespace. Docker remains the default runtime. The kind configuration and exact input hashes are in [`deploy/kind/VERSIONS.md`](../deploy/kind/VERSIONS.md); the scripted acceptance run is [`scripts/kind_e2e.py`](../scripts/kind_e2e.py). As of 2026-10-23 IST, the code and Helm chart have passed local tests and Helm lint, but the kind end-to-end check has **not run**. Do not describe this package as live verified until `docs/results/kind_e2e.md` and `results/live-checks/kind_e2e.json` contain a passing run for the reported commit.

## Runtime and deployment

`RUNTIME=kubernetes` selects the namespaced `KubernetesDriver`; unset or `docker` selects the existing Docker executor through an adapter. `METRICS_SOURCE=kubernetes` selects Kubernetes Prometheus and Deployment/Pod readers. `KUBERNETES_NAMESPACE` must be in the loaded rulebook's `namespaces` list. The Helm chart sets all three values. It deploys one brain replica, a ClusterIP Service, a mounted rulebook ConfigMap and a ServiceAccount. There is no Ingress or leader election.

The chart defaults to **watch** mode. Its namespaced Role grants get/list/watch on Deployments, Deployment scale, ReplicaSets, Pods, Events and Services. Ask and autopilot modes add patch/update on the named apps resources and delete on Pods. There is no ClusterRole, Secret API permission, `pods/exec`, or permission in `kube-system`. The chart never creates a Secret containing token data. Outside watch mode, `approvalToken.existingSecret` is required; its `token` key is read into `ETERNALAI_APPROVAL_TOKEN`. `prometheus.existingSecret` optionally supplies a bearer token through a `token` key.

For a local kind run, use only the assigned Docker window in `docs/COORDINATION.md` and follow `D:\eAI\STACK_LOCK.md`. The scripted check verifies the lock and resource state, takes the lock, creates only kind cluster `eai`, and tears it down in `finally`. It leaves Compose stopped. The command is:

```powershell
cd D:\eAI\eAI-k8s
.\.venv\Scripts\python.exe scripts\kind_e2e.py
```

The script requires the checksum-verified `D:\eAI\tools\kind.exe` and `helm.exe`, and a `kubectl` and Docker CLI. It pins the kind node image, Prometheus chart and Online Boutique v0.10.7 manifest; it refuses a changed manifest checksum. It builds `eai/eternalai:k8s-dev`, never the Compose `:v2` tag. All port-forwards use 18080-18082. Approval credentials are generated for the run, supplied to Kubernetes through stdin, and never printed. The script records PASS/FAIL details and the code/image revision in the result files above.

To render the chart without a cluster:

```powershell
& D:\eAI\tools\helm.exe lint deploy\helm\eternalai
& D:\eAI\tools\helm.exe template eternalai deploy\helm\eternalai -n eternalai
```

To install in another cluster, first provide a compatible rulebook with `namespaces` matching `values.namespaces`, a reachable Prometheus URL, the specified image, and an existing token Secret if approvals are needed. Install with `helm install eternalai deploy/helm/eternalai -n eternalai --create-namespace`. The ServiceAccount needs RoleBindings in each allowed namespace; the chart creates those namespaced bindings. Never place an approval token literal in Helm values.

## What the minimal driver does

`restart_service` patches the Deployment pod-template `kubectl.kubernetes.io/restartedAt` annotation, causing a rolling restart. `recreate_container` deletes one Pod owned by the target Deployment's ReplicaSet so the controller replaces it. `rollback_release` patches the Deployment template from its highest earlier owned ReplicaSet revision; policy marks this high-risk and requires approval. `scale_to()` patches the Deployment scale subresource, but scaling is **not** a rulebook runbook. `clear_temp_path`, pause rollout, change limits, patch HPA, cordon node and create Job raise `NotSupported` and are audited. The driver never calls a Secret API or deletes Deployments, Namespaces or PVCs. Every attempted driver action writes a local audit record.

The service graph comes from `eternalai.io/depends-on` Deployment annotations. [`deploy/online-boutique/annotate.ps1`](../deploy/online-boutique/annotate.ps1) and its shell twin apply the pinned graph. If discovery fails or is empty, the loader uses the static demo-shop graph and sets `config.TOPOLOGY_FALLBACK`. Bare Deployment names across multiple allowed namespaces are ambiguous; discovery also falls back in that case. This minimal runtime is designed for the single `shop` namespace.

Kubernetes telemetry preserves the Docker collector's twelve column names. cAdvisor and kube-state-metrics supply CPU, memory, memory limit, Pod readiness, restarts and Deployment-generation changes. Online Boutique does not expose the demo shop's request rate, HTTP error rate, p95 latency, dependency-failure rate, error-log rate or scratch bytes by default; these six columns remain **NaN**, not zero. Failed Prometheus queries are recorded separately from absent series. Pod status supplies OOM and failed-image-pull evidence; the minimal Role deliberately cannot read Pod logs.

The saved detector, classifier and ranker artifacts belong to the Docker demo shop. When they do not cover the discovered Kubernetes services, `/status` reports model fallbacks and the brain uses a live baseline, rule diagnosis and graph-based root fallback. A new-revision Pod with `ImagePullBackOff`, `ErrImagePull` or `InvalidImageName` is direct Kubernetes-only evidence for `bad_deploy`, which proposes the existing approval-gated rollback. Recovery verification requires the target and all graph callers to have every replica Ready, plus HTTP 200 from the frontend throughout the observation window. No Online Boutique result is claimed here until the scripted kind check passes.

This is a single-brain, single-namespace demonstration. It does not install Chaos Mesh or a production monitoring stack, run Sock Shop or Train Ticket, perform leader election, or add the later policy runbooks. Missing HTTP metrics and Docker-trained models limit diagnosis quality beyond the explicit bad-image path. The kind script's live result, rather than unit tests, is the acceptance evidence for behavior against a real cluster.
