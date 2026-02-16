"""Tests for backend.collectors.log_collector."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.collectors.log_collector import LogCollector
from backend.engine.event_bus import EventBus
from backend.models.event import EventSource, EventType


@pytest.fixture
def event_bus():
    return EventBus()


def _make_collector(event_bus, log_file, **kwargs):
    """Create a LogCollector that always uses the Linux code path."""
    collector = LogCollector(event_bus, interval=1.0, **kwargs)
    collector._log_path = log_file
    return collector


class TestLogCollector:
    @pytest.mark.asyncio
    async def test_counts_failures_from_log(self, event_bus, tmp_path):
        log_file = tmp_path / "auth.log"
        log_file.write_text(
            "Jan 1 00:00:01 host sshd[1234]: Failed password for root\n"
            "Jan 1 00:00:02 host sshd[1234]: Failed password for admin\n"
            "Jan 1 00:00:03 host sshd[1234]: Accepted password for user\n"
            "Jan 1 00:00:04 host sshd[1234]: authentication failure; user=test\n"
        )
        collector = _make_collector(event_bus, log_file, window_seconds=60.0)

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events = await collector.collect()
        assert len(events) == 1
        assert events[0].source == EventSource.LOG_COLLECTOR
        assert events[0].event_type == EventType.LOGIN_FAILED
        assert events[0].payload["failed_logins"] == 3  # 2 failed password + 1 auth failure

    @pytest.mark.asyncio
    async def test_no_failures_no_event(self, event_bus, tmp_path):
        log_file = tmp_path / "auth.log"
        log_file.write_text("Jan 1 00:00:01 host sshd[1234]: Accepted password for user\n")
        collector = _make_collector(event_bus, log_file)

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events = await collector.collect()
        assert events == []

    @pytest.mark.asyncio
    async def test_reads_incrementally(self, event_bus, tmp_path):
        log_file = tmp_path / "auth.log"
        log_file.write_text("Jan 1 00:00:01 host sshd: Failed password for root\n")
        collector = _make_collector(event_bus, log_file, window_seconds=60.0)

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events1 = await collector.collect()
        assert events1[0].payload["failed_logins"] == 1

        # Append more lines
        with open(log_file, "a") as f:
            f.write("Jan 1 00:00:05 host sshd: Failed password for admin\n")
            f.write("Jan 1 00:00:06 host sshd: Failed password for test\n")

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events2 = await collector.collect()
        # Now 1 (still in window) + 2 new = 3
        assert events2[0].payload["failed_logins"] == 3

    @pytest.mark.asyncio
    async def test_window_expiry(self, event_bus, tmp_path):
        log_file = tmp_path / "auth.log"
        log_file.write_text("Jan 1 00:00:01 host sshd: Failed password for root\n")
        collector = _make_collector(event_bus, log_file, window_seconds=2.0)

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events1 = await collector.collect()
        assert events1[0].payload["failed_logins"] == 1

        # Backdate all failure timestamps to simulate expiry
        collector._failure_timestamps = [time.time() - 10]

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events2 = await collector.collect()
        assert events2 == []  # all expired

    @pytest.mark.asyncio
    async def test_missing_log_file(self, event_bus, tmp_path):
        collector = _make_collector(event_bus, tmp_path / "nonexistent.log")

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events = await collector.collect()
        assert events == []

    @pytest.mark.asyncio
    async def test_no_log_path_returns_empty(self, event_bus):
        collector = LogCollector(event_bus, interval=1.0)
        collector._log_path = None

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events = await collector.collect()
        assert events == []

    @pytest.mark.asyncio
    async def test_payload_fields(self, event_bus, tmp_path):
        log_file = tmp_path / "auth.log"
        log_file.write_text("sshd: Failed password for root\n")
        collector = _make_collector(event_bus, log_file, window_seconds=60.0)

        with patch("backend.collectors.log_collector.platform.system", return_value="Linux"):
            events = await collector.collect()
        p = events[0].payload
        assert "failed_logins" in p
        assert "window_seconds" in p
        assert p["window_seconds"] == 60.0
