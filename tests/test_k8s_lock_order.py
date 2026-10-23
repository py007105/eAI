"""A failed preflight must not touch a shared stack before ownership or stop another owner's stack."""

from scripts import compose_regression_k8s, kind_e2e


def test_kind_claims_lock_before_docker_inspection_and_releases_on_failure(monkeypatch, tmp_path):
    calls = []
    kind = tmp_path / "kind.exe"
    helm = tmp_path / "helm.exe"
    kind.touch()
    helm.touch()
    monkeypatch.setattr(kind_e2e, "KIND", kind)
    monkeypatch.setattr(kind_e2e, "HELM", helm)
    monkeypatch.setattr(kind_e2e, "is_free", lambda: True)
    monkeypatch.setattr(kind_e2e, "free_memory_gb", lambda: 8)
    monkeypatch.setattr(kind_e2e, "take", lambda *args: calls.append("take"))
    monkeypatch.setattr(kind_e2e, "release", lambda *args: calls.append("release"))
    monkeypatch.setattr(kind_e2e, "write_results", lambda *args: None)
    monkeypatch.setattr(kind_e2e, "CHECKS", [])

    def command(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            return "candidate-commit"
        calls.append("docker-inspection")
        raise RuntimeError("inspection failed")

    monkeypatch.setattr(kind_e2e, "cmd", command)
    assert kind_e2e.main() == 1
    assert calls == ["take", "docker-inspection", "release"]


def test_compose_does_not_stop_a_stack_it_found_running(monkeypatch, tmp_path):
    (tmp_path / ".env").touch()
    calls = []
    monkeypatch.setattr(compose_regression_k8s, "ROOT", tmp_path)
    monkeypatch.setattr(compose_regression_k8s, "is_free", lambda: True)
    monkeypatch.setattr(compose_regression_k8s, "free_memory_gb", lambda: 4)
    monkeypatch.setattr(compose_regression_k8s, "take", lambda *args: calls.append("take"))
    monkeypatch.setattr(compose_regression_k8s, "release", lambda *args: calls.append("release"))
    monkeypatch.setattr(compose_regression_k8s, "write_results", lambda *args: None)
    monkeypatch.setattr(compose_regression_k8s, "CHECKS", [])

    def command(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            return "candidate-commit"
        calls.append(args)
        if args[:2] == ["docker", "ps"]:
            return "already-running-container"
        raise AssertionError("no other command should run")

    monkeypatch.setattr(compose_regression_k8s, "command", command)
    assert compose_regression_k8s.main() == 1
    assert calls[0] == "take"
    assert calls[1][:2] == ["docker", "ps"]
    assert calls[2] == "release"
    assert len(calls) == 3
