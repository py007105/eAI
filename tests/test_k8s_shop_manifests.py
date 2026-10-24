"""deploy/kind/shop/*.yaml match our Compose shop, config.TOPOLOGY and the Docker-style Prometheus labels."""
from pathlib import Path

import yaml

from eternalai import config

ROOT = Path(__file__).resolve().parents[1]
SHOP = ROOT / "deploy/kind/shop/shop.yaml"
PROM = ROOT / "deploy/kind/shop/prometheus.yaml"
APPS = ("web", "orders", "payments", "inventory")


def docs(path):
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def by_kind(items, kind, namespace=None):
    return {d["metadata"]["name"]: d for d in items
            if d["kind"] == kind and (namespace is None or d["metadata"].get("namespace") == namespace)}


def compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def mebibytes(text):
    assert text.endswith("Mi"), text
    return int(text[:-2])


def test_shop_namespace_holds_exactly_the_trained_services():
    deployments = by_kind(docs(SHOP), "Deployment", "shop")
    assert set(deployments) == set(config.TOPOLOGY) == set(APPS)   # the models only fit these names
    assert set(by_kind(docs(SHOP), "Service", "shop")) == set(APPS)


def test_annotations_match_static_topology():
    for name, d in by_kind(docs(SHOP), "Deployment", "shop").items():
        raw = d["metadata"]["annotations"]["eternalai.io/depends-on"]
        assert [s for s in raw.split(",") if s] == config.TOPOLOGY[name]


def test_app_containers_use_local_images_compose_limits_and_no_secret_values():
    c = compose()
    for name, d in by_kind(docs(SHOP), "Deployment", "shop").items():
        spec = d["spec"]["template"]["spec"]
        (container,) = spec["containers"]
        assert container["image"] == c["services"][name]["image"] == f"eai/{name}:v1"
        assert container["imagePullPolicy"] == "Never"
        assert mebibytes(container["resources"]["limits"]["memory"]) == 256 and c["x-app"]["mem_limit"] == "256m"
        assert container["readinessProbe"]["httpGet"]["path"] == "/healthz"
        assert "livenessProbe" not in container           # recovery is EternalAI's job (Compose restart: "no")
        env = {e["name"]: e for e in container["env"]}
        assert env["CHAOS_TOKEN"]["valueFrom"]["secretKeyRef"] == {"name": "shop-chaos", "key": "token"}
        assert "value" not in env["CHAOS_TOKEN"]
        assert d["spec"]["template"]["metadata"]["labels"] == {"app": name, "eai.role": "app"}
        assert d["spec"]["selector"]["matchLabels"] == {"app": name}


def test_loadgen_is_outside_the_shop_namespace_with_compose_settings():
    c = compose()["services"]["loadgen"]
    (d,) = by_kind(docs(SHOP), "Deployment", "loadgen").values()
    (container,) = d["spec"]["template"]["spec"]["containers"]
    assert container["image"] == c["image"] == "eai/loadgen:v1" and container["imagePullPolicy"] == "Never"
    env = {e["name"]: e["value"] for e in container["env"]}
    assert env["TARGET_URL"] == "http://web.shop.svc.cluster.local:8000"
    assert env["BASE_RPS"] == "6" and "BASE_RPS:-6" in c["environment"]["BASE_RPS"]
    assert mebibytes(container["resources"]["limits"]["memory"]) == 128 and c["mem_limit"] == "128m"


def test_no_manifest_contains_a_secret_object():
    assert not [d for d in docs(SHOP) + docs(PROM) if d["kind"] == "Secret"]


def test_prometheus_is_plain_and_matches_compose_image_and_interval():
    items = docs(PROM)
    (d,) = by_kind(items, "Deployment", "monitoring").values()
    (container,) = d["spec"]["template"]["spec"]["containers"]
    assert container["image"] == compose()["services"]["prometheus"]["image"]
    assert not [i for i in items if i["kind"] in ("ClusterRole", "ClusterRoleBinding")]
    roles = [i for i in items if i["kind"] == "Role"]
    assert sorted(r["metadata"]["namespace"] for r in roles) == ["loadgen", "shop"]
    for r in roles:
        assert r["rules"] == [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list", "watch"]}]
    cfg = yaml.safe_load(by_kind(items, "ConfigMap")["prometheus-config"]["data"]["prometheus.yml"])
    compose_cfg = yaml.safe_load((ROOT / "telemetry/prometheus.yml").read_text(encoding="utf-8"))
    assert cfg["global"]["scrape_interval"] == compose_cfg["global"]["scrape_interval"] == "2s"


def test_prometheus_labels_match_the_docker_queries():
    items = docs(PROM)
    cfg = yaml.safe_load(by_kind(items, "ConfigMap")["prometheus-config"]["data"]["prometheus.yml"])
    jobs = {j["job_name"]: j for j in cfg["scrape_configs"]}
    assert set(jobs) == {"app", "loadgen"}            # the same job names as telemetry/prometheus.yml
    app = jobs["app"]
    assert app["kubernetes_sd_configs"] == [{"role": "pod", "namespaces": {"names": ["shop"]}}]
    targets = {r.get("target_label"): r for r in app["relabel_configs"] if r.get("target_label")}
    assert targets["instance_name"]["source_labels"] == ["__meta_kubernetes_pod_label_app"]
    assert targets["instance"]["replacement"] == "${1}:8000"
    keep = [r for r in app["relabel_configs"] if r.get("action") == "keep"]
    assert {"source_labels": ["__meta_kubernetes_pod_label_eai_role"], "regex": "app", "action": "keep"} in keep
    # eternalai/collector.py Q selects job="app" and instance_name="<service>"
    from eternalai.collector import Q
    assert 'job="app",instance_name="{s}"' in Q["up"]
