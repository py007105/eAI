"""preflight checks with mocks only: no Docker, no network, no git against the real repo."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("preflight", Path(__file__).resolve().parents[1] / "tools" / "preflight.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)


class FakeContainers:
    def __init__(self, env):
        self.env = env

    def list(self, filters=None):
        return [] if self.env is None else [SimpleNamespace(attrs={"Config": {"Env": self.env}})]


class ServiceContainers:
    """Service-aware fake: `services` maps a compose service name to its environment list; absent services return no container."""
    def __init__(self, services):
        self.services = services

    def list(self, filters=None):
        name = filters["label"].split("=", 1)[1]
        return [SimpleNamespace(attrs={"Config": {"Env": self.services[name]}})] if name in self.services else []


T3_APPS = {n: ["OTEL_SDK_DISABLED=true"] for n in ("web", "orders", "inventory", "payments")}


def t3_client(**extra):
    return SimpleNamespace(containers=ServiceContainers({**T3_APPS, **extra}))


def test_telemetry_condition_t3_passes_fails_and_reports_dashboard_as_info():
    ok, detail = pf.check_telemetry_condition(lambda: t3_client())
    assert ok and "condition T3 holds" in detail and "dashboard not running" in detail
    ok, detail = pf.check_telemetry_condition(lambda: t3_client(dashboard=["X=1"]))
    assert ok and "documented difference" in detail                                  # dashboard on is INFO, not a failure
    assert not pf.check_telemetry_condition(lambda: t3_client(jaeger=["X=1"]))[0]
    bad = {**T3_APPS, "web": ["OTEL_SDK_DISABLED=false"]}
    ok, detail = pf.check_telemetry_condition(lambda: SimpleNamespace(containers=ServiceContainers(bad)))
    assert not ok and "web" in detail
    assert not pf.check_telemetry_condition(lambda: SimpleNamespace(containers=ServiceContainers({})))[0]   # apps not running


class FakeClient:
    def __init__(self, env=("A=1",), ping_ok=True):
        self.containers, self._ok = FakeContainers(None if env is None else list(env)), ping_ok

    def ping(self):
        if not self._ok:
            raise ConnectionError("down")
        return True


def test_docker_down_fails_and_up_passes():
    assert pf.check_docker(lambda: FakeClient(ping_ok=False))[0] is False
    assert pf.check_docker(lambda: FakeClient())[0] is True


def test_models_missing_is_reported_by_name():
    ok, d = pf.check_models(lambda n: (None, None) if n == "ranker" else (object(), {}))
    assert not ok and "ranker" in d
    assert pf.check_models(lambda n: (object(), {}))[0]


def test_token_default_and_empty_fail_real_passes_and_value_is_not_in_detail():
    assert not pf.check_token({"ETERNALAI_APPROVAL_TOKEN": "change-me"})[0]
    assert not pf.check_token({})[0]
    ok, d = pf.check_token({"ETERNALAI_APPROVAL_TOKEN": "s3cret-value"})
    assert ok and "s3cret-value" not in d
    assert not pf.check_token(None)[0]


def test_llm_key_presence_only_never_value_and_groq_never_required():
    env = {"GEMINI_API_KEY": "TOPSECRET", "GROQ_API_KEY": ""}
    ok, d = pf.check_llm_keys(env, require=True)
    assert ok and "TOPSECRET" not in d and "GROQ_API_KEY ABSENT" in d
    assert not pf.check_llm_keys({"GEMINI_API_KEY": ""}, require=True)[0]
    assert pf.check_llm_keys({"GEMINI_API_KEY": ""}, require=False)[0]


def test_scorecard_must_be_empty_and_unreachable_fails():
    assert pf.check_scorecard_empty(lambda u: {"runs": 0})[0]
    assert not pf.check_scorecard_empty(lambda u: {"runs": 12})[0]

    def boom(u):
        raise OSError

    assert not pf.check_scorecard_empty(boom)[0]


def test_inventory_stock_check_refuses_below_threshold_and_when_unreadable():
    assert pf.check_inventory_stock(lambda: {"sku-mug": 100000, "sku-bag": 90000})[0]
    ok, d = pf.check_inventory_stock(lambda: {"sku-mug": 100000, "sku-bag": 0})
    assert not ok and "sku-bag" in d and "stock_gate.py --restock" in d
    assert not pf.check_inventory_stock(lambda: {})[0]

    def boom():
        raise RuntimeError

    assert not pf.check_inventory_stock(boom)[0]


def test_tag_check_detects_missing_tag_and_code_difference():
    def runner(files, rc=0):
        return lambda args: SimpleNamespace(returncode=rc if args[1] == "rev-parse" else 0, stdout="\n".join(files))

    assert pf.check_tag("t", runner([]))[0]
    ok, d = pf.check_tag("t", runner(["engine/engine.py"]))
    assert not ok and "engine.py" in d
    assert not pf.check_tag("t", runner([], rc=1))[0]


def test_run_all_with_everything_mocked_passes_and_skips_env_when_docker_down():
    env = ["ETERNALAI_APPROVAL_TOKEN=real", "GEMINI_API_KEY=k"]
    ok = lambda args: SimpleNamespace(returncode=0, stdout="")  # noqa: E731
    class Full(FakeClient):
        def __init__(self):
            self.containers, self._ok = ServiceContainers({**T3_APPS, "eternalai": env}), True
    res = pf.run_all(True, "t", Full, lambda u: {"runs": 0}, lambda n: (object(), {}), ok, lambda: {"sku-mug": 100000})
    assert all(r[1][0] for r in res) and len(res) == 8
    res = pf.run_all(True, "t", lambda: FakeClient(env, ping_ok=False), lambda u: {"runs": 0}, lambda n: (object(), {}), ok)
    d = dict(res)
    assert not d["docker daemon"][0] and not d["approval token"][0]
