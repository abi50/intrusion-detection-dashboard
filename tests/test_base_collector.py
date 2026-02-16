from __future__ import annotations

import asyncio

import pytest

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


class StubCollector(BaseCollector):
    """Collector that returns a fixed event each cycle."""

    name = "stub"

    def __init__(self, event_bus: EventBus, interval: float = 0.1) -> None:
        super().__init__(event_bus, interval=interval)
        self.collect_count = 0

    async def collect(self) -> list[Event]:
        self.collect_count += 1
        return [
            Event(
                source=EventSource.CPU_COLLECTOR,
                event_type=EventType.CPU_USAGE,
                payload={"percent": 42.0, "cycle": self.collect_count},
            )
        ]


class ErrorCollector(BaseCollector):
    """Collector that raises on every collect call."""

    name = "error"

    async def collect(self) -> list[Event]:
        raise RuntimeError("collect failed")


class EmptyCollector(BaseCollector):
    """Collector that returns no events."""

    name = "empty"

    async def collect(self) -> list[Event]:
        return []


# ── basic lifecycle ─────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_publishes_events():
    """Collector publishes events to the bus each cycle."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = StubCollector(bus, interval=0.1)
    await collector.start()

    await asyncio.sleep(0.35)  # should get ~3 cycles
    await collector.stop()
    await bus.stop()

    assert len(received) >= 2
    assert all(e.payload["percent"] == 42.0 for e in received)


@pytest.mark.asyncio
async def test_collector_start_stop_idempotent():
    bus = EventBus()
    collector = StubCollector(bus)

    await collector.start()
    await collector.start()  # double start
    assert collector.running is True

    await collector.stop()
    await collector.stop()  # double stop
    assert collector.running is False


@pytest.mark.asyncio
async def test_collector_stop_is_graceful():
    """Stop cancels the loop without raising."""
    bus = EventBus()
    collector = StubCollector(bus, interval=0.05)

    await collector.start()
    await asyncio.sleep(0.15)
    await collector.stop()

    assert collector.running is False
    assert collector.collect_count >= 1


# ── error resilience ────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_survives_collect_error():
    """A failing collect() doesn't kill the collector loop."""
    bus = EventBus()
    collector = ErrorCollector(bus, interval=0.05)

    await collector.start()
    await asyncio.sleep(0.2)
    await collector.stop()

    # If we got here without exception, the loop survived
    assert collector.running is False


# ── empty collect ───────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_collect_publishes_nothing():
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = EmptyCollector(bus, interval=0.1)
    await collector.start()

    await asyncio.sleep(0.25)
    await collector.stop()
    await bus.stop()

    assert len(received) == 0


# ── custom interval ─────────────────────────────────────


@pytest.mark.asyncio
async def test_custom_interval_override():
    bus = EventBus()
    collector = StubCollector(bus, interval=99.0)
    assert collector.interval == 99.0
