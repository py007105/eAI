"""Compose regression evidence remains tied to one candidate and execution."""

import json

import pytest

from scripts import compose_regression_k8s


def test_compose_result_files_are_unique_and_keep_failed_checks(monkeypatch, tmp_path):
    for relative in ("docker-compose.yml", "eternalai/rulebooks/default.yaml"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    monkeypatch.setattr(compose_regression_k8s, "ROOT", tmp_path)
    monkeypatch.setattr(compose_regression_k8s, "CHECKS", [
        {"check": "preflight: benchmark tag", "result": "FAIL", "detail": "branch changed", "t": "t"}])

    md, raw = compose_regression_k8s.write_results(
        "candidate-commit", "run-123", "start IST", {"eai/eternalai:v2": "sha256:image-id"})
    result = json.loads(raw.read_text(encoding="utf-8"))
    assert md.name == "compose_regression_k8s_run-123.md"
    assert result["execution_id"] == "run-123"
    assert result["commit"] == "candidate-commit"
    assert result["images"]["eai/eternalai:v2"] == "sha256:image-id"
    assert result["checks"][0]["result"] == "FAIL"
    with pytest.raises(FileExistsError):
        compose_regression_k8s.write_results("candidate-commit", "run-123", "start IST", {})
