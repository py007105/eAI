# Pinned kind acceptance inputs

All checksums below were checked on 2026-10-23 IST before kind was run. The kind and Helm binaries live in `D:\eAI\tools`, outside Git. The Prometheus chart archive was downloaded into ignored `runtime/`; the live script verifies that archive before installing it, or pulls and verifies the same version if the archive is absent.

| Input | Version/source | SHA256 or OCI digest |
|---|---|---|
| kind Windows amd64 binary | [v0.33.0 official release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0), `kind-windows-amd64` | `4b22adaa135368c5a465d56bbd8e520cbea87272a06ca00b6078e7b81515c9fc` (matches same-release `.sha256sum`) |
| Helm Windows amd64 zip | [v3.21.3 official release](https://github.com/helm/helm/releases/tag/v3.21.3), `helm-v3.21.3-windows-amd64.zip` | `ff490897e07e976c65a9bd7690cfc139b35ba5e8f25d00eaf1e53a30f1ad3f62` (matches official `.sha256sum`) |
| kind node image | `kindest/node:v1.37.0` in the [kind v0.33.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0) | OCI digest `sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5` |
| Prometheus Helm chart | `oci://ghcr.io/prometheus-community/charts/prometheus:29.18.0` | OCI digest `sha256:b532a4cd15cf948aea5ce5405d586b789b4cbb90d2bef5209bbaffe6239b7956`; pulled `.tgz` SHA256 `24f5f056dd5cb00e98ffb905c9c2779e810153f1b5a6306bf2cc2c5a4f02a0b9` |
| Online Boutique release manifest | [v0.10.7 `release/kubernetes-manifests.yaml`](https://github.com/GoogleCloudPlatform/microservices-demo/blob/v0.10.7/release/kubernetes-manifests.yaml) | downloaded manifest SHA256 `ae3c20181c051048e6a5cae51fa530681affa4043ba60ae95d4f39e1262f2744` |

The two Windows binaries and chart archive were hashed locally. The node image digest is published by kind and is pinned in `kind-cluster.yaml`; its actual pull and use await the assigned live window. The Online Boutique manifest hash is enforced by `scripts/kind_e2e.py` before applying it.
