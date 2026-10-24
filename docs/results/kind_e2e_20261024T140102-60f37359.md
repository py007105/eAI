# Kubernetes kind end-to-end check

- Execution: `20261024T140102-60f37359`
- Time: 2026-10-24 14:01:02 IST to 2026-10-24 14:14:11 IST
- Commit: `68c6d1d8f6c758a5231b48878ec93cd986c3a6c9`
- Image: `eai/eternalai:k8s-dev` (`not built`)
- Configuration: [JSON result](../../results/live-checks/kind_e2e_20261024T140102-60f37359.json)

| Check | Result | Detail |
|---|---|---|
| preflight | PASS | Compose stopped, no kind cluster, 6.30 GiB free |
| cluster | PASS | pinned single-node kind cluster created |
| aborted | FAIL | RuntimeError |
| teardown | PASS | only the eai kind cluster removed |
| lock_release | PASS | atomic owner file released |
