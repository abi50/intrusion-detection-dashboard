from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from backend.collectors.cpu_collector import CpuCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event


@pytest.mark.asyncio
async def test_emits_reading_every_cycle():
    """Each collect() always emits at least one CPU reading event."""
    bus = EventBus()
    collector = CpuCollector(bus, interval=1.0, spike_threshold=90.0)

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 25.0
        events = await collector.collect()

    assert len(events) == 1
    assert events[0].payload["percent"] == 25.0
    assert events[0].payload["sustained"] is False


@pytest.mark.asyncio
async def test_no_spike_event_below_threshold():
    """No sustained spike event when CPU is below threshold."""
    bus = EventBus()
    collector = CpuCollector(bus, spike_threshold=90.0, sustained_seconds=5.0)

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 50.0
        for _ in range(5):
            events = await collector.collect()
            sustained = [e for e in events if e.payload.get("sustained")]
            assert len(sustained) == 0


@pytest.mark.asyncio
async def test_spike_only_after_sustained_period():
    """Spike event fires only after CPU exceeds threshold for sustained_seconds."""
    bus = EventBus()
    collector = CpuCollector(
        bus, spike_threshold=80.0, sustained_seconds=1.0
    )

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 95.0

        # First call starts the timer
        events = await collector.collect()
        sustained = [e for e in events if e.payload.get("sustained")]
        assert len(sustained) == 0

        # Wait past the sustained period
        await asyncio.sleep(1.1)

        # Now it should fire
        events = await collector.collect()
        sustained = [e for e in events if e.payload.get("sustained")]
        assert len(sustained) == 1
        assert sustained[0].payload["duration_seconds"] >= 1.0


@pytest.mark.asyncio
async def test_spike_resets_when_cpu_drops():
    """Spike timer resets when CPU drops below threshold."""
    bus = EventBus()
    collector = CpuCollector(
        bus, spike_threshold=80.0, sustained_seconds=0.5
    )

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        # Go above threshold
        mock_psutil.cpu_percent.return_value = 95.0
        await collector.collect()
        await asyncio.sleep(0.3)

        # Drop below — should reset timer
        mock_psutil.cpu_percent.return_value = 40.0
        await collector.collect()
        assert collector._spike_start is None

        # Go above again — timer restarts from zero
        mock_psutil.cpu_percent.return_value = 95.0
        await collector.collect()
        events = await collector.collect()
        sustained = [e for e in events if e.payload.get("sustained")]
        assert len(sustained) == 0  # not enough time yet


@pytest.mark.asyncio
async def test_end_to_end_with_bus():
    """CpuCollector publishes events through the EventBus."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = CpuCollector(bus, interval=0.1, spike_threshold=99.0)

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 30.0
        await collector.start()
        await asyncio.sleep(0.35)
        await collector.stop()

    await bus.stop()

    assert len(received) >= 2
    assert all(e.source == "cpu_collector" for e in received)
