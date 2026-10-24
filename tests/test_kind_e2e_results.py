"""Live-check evidence must identify one execution and the inputs it actually used."""

import json
import sys

import pytest

from scripts import kind_e2e


def test_cli_output_decodes_invalid_utf8_without_losing_command_status(tmp_path, monkeypatch):
    monkeypatch.setattr(kind_e2e, "ROOT", tmp_path)
    output = kind_e2e.cmd([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([0x8f]))"])
    assert output == "\ufffd"


def test_monitoring_status_keeps_reasons_but_not_messages(monkeypatch):
    body = {"items": [{"metadata": {"name": "prometheus-server-1"}, "status": {
        "phase": "Pending", "conditions": [{"type": "PodScheduled", "status": "False",
                                              "reason": "Unschedulable", "message": "private cluster detail"}],
        "containerStatuses": [{"ready": False, "state": {"waiting": {
            "reason": "ImagePullBackOff", "message": "private registry detail"}}}]}}]}
    monkeypatch.setattr(kind_e2e, "cmd", lambda *args, **kwargs: json.dumps(body))
    status = kind_e2e.monitoring_pod_status()
    assert "Unschedulable" in status
    assert "ImagePullBackOff" in status
    assert "private" not in status


def test_kind_results_are_execution_specific_and_do_not_overwrite(monkeypatch, tmp_path):
    for relative in ("deploy/kind/kind-cluster.yaml", "deploy/helm/eternalai/values.yaml"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(relative, encoding="utf-8")
    monkeypatch.setattr(kind_e2e, "ROOT", tmp_path)
    monkeypatch.setattr(kind_e2e, "LATEST_MD", tmp_path / "docs/results/kind_e2e.md")
    monkeypatch.setattr(kind_e2e, "LATEST_JSON", tmp_path / "results/live-checks/kind_e2e.json")
    monkeypatch.setattr(kind_e2e, "CHECKS", [{"check": "cluster", "result": "FAIL", "detail": "unready", "t": "t"}])

    md, raw = kind_e2e.write_results("candidate-commit", "run-123", "start IST", None)
    data = json.loads(raw.read_text(encoding="utf-8"))
    assert md.name == "kind_e2e_run-123.md"
    assert raw.name == "kind_e2e_run-123.json"
    assert data["execution_id"] == "run-123"
    assert data["commit"] == "candidate-commit"
    assert data["image"]["id"] is None
    assert data["checks"][0]["result"] == "FAIL"
    assert data["configuration"]["kind_config_sha256"] == kind_e2e.file_hash(tmp_path / "deploy/kind/kind-cluster.yaml")
    assert json.loads(kind_e2e.LATEST_JSON.read_text(encoding="utf-8")) == data
    with pytest.raises(FileExistsError):
        kind_e2e.write_results("candidate-commit", "run-123", "start IST", None)
