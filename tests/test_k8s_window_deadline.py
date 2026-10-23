"""Scheduled work must stop starting commands before cleanup time."""

from datetime import datetime, timedelta

import pytest

from scripts import k8s_window_deadline as deadline


def test_scheduled_command_timeout_is_capped_and_cleanup_is_exempt(monkeypatch):
    future = datetime.now(deadline.IST) + timedelta(seconds=30)
    monkeypatch.setenv(deadline.ENV, future.isoformat())
    assert 0 < deadline.bounded_timeout(300) <= 30
    assert deadline.bounded_timeout(300, cleanup=True) == 300


def test_expired_or_naive_deadline_blocks_new_work(monkeypatch):
    past = datetime.now(deadline.IST) - timedelta(seconds=5)
    monkeypatch.setenv(deadline.ENV, past.isoformat())
    with pytest.raises(TimeoutError):
        deadline.bounded_timeout(1)
    monkeypatch.setenv(deadline.ENV, "2026-10-24T11:15:00")
    with pytest.raises(ValueError):
        deadline.bounded_timeout(1)
