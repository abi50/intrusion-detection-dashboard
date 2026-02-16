"""Tests for backend.collectors.process_collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.collectors.process_collector import ProcessCollector
from backend.engine.event_bus import EventBus
from backend.models.event import EventSource, EventType


def _mock_proc(pid: int, name: str, username: str = "user") -> MagicMock:
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "username": username}
    return proc


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def collector(event_bus):
    return ProcessCollector(event_bus, interval=1.0)


class TestProcessCollector:
    @pytest.mark.asyncio
    async def test_emits_events_for_new_processes(self, collector):
        procs = [_mock_proc(1, "python"), _mock_proc(2, "nc")]
        with patch("backend.collectors.process_collector.psutil.process_iter", return_value=procs):
            events = await collector.collect()
        assert len(events) == 2
        assert all(e.source == EventSource.PROCESS_COLLECTOR for e in events)
        assert all(e.event_type == EventType.PROCESS_RUNNING for e in events)
        names = {e.payload["name"] for e in events}
        assert names == {"python", "nc"}

    @pytest.mark.asyncio
    async def test_only_alerts_on_new_pids(self, collector):
        procs = [_mock_proc(1, "python"), _mock_proc(2, "nc")]
        with patch("backend.collectors.process_collector.psutil.process_iter", return_value=procs):
            events1 = await collector.collect()
            events2 = await collector.collect()
        assert len(events1) == 2
        assert len(events2) == 0  # same PIDs, no new events

    @pytest.mark.asyncio
    async def test_alerts_again_when_pid_reappears(self, collector):
        procs1 = [_mock_proc(1, "python")]
        procs2 = [_mock_proc(2, "bash")]  # PID 1 gone, PID 2 new
        procs3 = [_mock_proc(1, "python"), _mock_proc(2, "bash")]  # PID 1 returns

        with patch("backend.collectors.process_collector.psutil.process_iter") as mock_iter:
            mock_iter.return_value = procs1
            await collector.collect()

            mock_iter.return_value = procs2
            events2 = await collector.collect()
            assert len(events2) == 1
            assert events2[0].payload["name"] == "bash"

            mock_iter.return_value = procs3
            events3 = await collector.collect()
            assert len(events3) == 1  # PID 1 is new again
            assert events3[0].payload["name"] == "python"

    @pytest.mark.asyncio
    async def test_payload_contains_required_fields(self, collector):
        procs = [_mock_proc(42, "mimikatz", "admin")]
        with patch("backend.collectors.process_collector.psutil.process_iter", return_value=procs):
            events = await collector.collect()
        payload = events[0].payload
        assert payload["name"] == "mimikatz"
        assert payload["pid"] == 42
        assert payload["username"] == "admin"

    @pytest.mark.asyncio
    async def test_name_is_lowercased(self, collector):
        procs = [_mock_proc(1, "Mimikatz")]
        with patch("backend.collectors.process_collector.psutil.process_iter", return_value=procs):
            events = await collector.collect()
        assert events[0].payload["name"] == "mimikatz"

    @pytest.mark.asyncio
    async def test_end_to_end_with_bus(self, event_bus):
        collector = ProcessCollector(event_bus, interval=0.1)
        received = []
        event_bus.subscribe(lambda e: received.append(e) or __import__("asyncio").sleep(0))

        procs = [_mock_proc(1, "python")]
        with patch("backend.collectors.process_collector.psutil.process_iter", return_value=procs):
            await event_bus.start()
            await collector.start()
            await __import__("asyncio").sleep(0.3)
            await collector.stop()
            await event_bus.stop()

        assert len(received) >= 1
        assert received[0].source == EventSource.PROCESS_COLLECTOR
