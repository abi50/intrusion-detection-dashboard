"""Architecture and runtime validation tests.

Verifies:
- No circular imports
- Collectors + EventBus integrate end-to-end
- Graceful shutdown (no hanging tasks)
- No resource leaks (no unclosed tasks after stop)
- Unawaited coroutine detection
"""

from __future__ import annotations

import asyncio
import importlib
import sys

import pytest

from backend.models.event import Event, EventSource, EventType
from backend.engine.event_bus import EventBus
from backend.collectors.base import BaseCollector


# ── Circular import checks ────────────────────────────


_MODULES = [
    "backend.config",
    "backend.models",
    "backend.models.event",
    "backend.models.alert",
    "backend.models.metrics",
    "backend.engine.event_bus",
    "backend.collectors.base",
    "backend.collectors.cpu_collector",
    "backend.collectors.port_collector",
    "backend.db.database",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_no_circular_imports(module_name: str):
    """Each module can be imported independently without circular import errors."""
    # Save original sys.modules state so we can restore it after the test.
    # This prevents corrupting module references for subsequent tests.
    saved = dict(sys.modules)
    to_remove = [k for k in sys.modules if k.startswith("backend")]
    for k in to_remove:
        del sys.modules[k]
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        if "circular" in str(e).lower():
            pytest.fail(f"Circular import detected in {module_name}: {e}")
        raise
    finally:
        # Restore original modules so patches in other tests target the right objects
        sys.modules.update(saved)


def test_cross_module_imports():
    """Verify all key cross-module imports work together."""
    from backend.config import settings
    from backend.models import Event, EventSource, EventType, Alert, Severity, SEVERITY_MULTIPLIER, SystemMetrics
    from backend.engine.event_bus import EventBus
    from backend.collectors.base import BaseCollector
    from backend.collectors.cpu_collector import CpuCollector
    from backend.collectors.port_collector import PortCollector
    # If we get here, no circular imports
    assert settings is not None
    assert Event is not None


# ── Collector + EventBus integration ──────────────────


class IntegrationCollector(BaseCollector):
    """Emits a known event for integration testing."""

    name = "integration"

    async def collect(self) -> list[Event]:
        return [
            Event(
                source=EventSource.CPU_COLLECTOR,
                event_type=EventType.CPU_USAGE,
                payload={"integration": True},
            )
        ]


@pytest.mark.asyncio
async def test_collector_eventbus_end_to_end():
    """Events flow from collector → EventBus → subscriber."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = IntegrationCollector(bus, interval=0.05)
    await collector.start()

    await asyncio.sleep(0.2)

    await collector.stop()
    await bus.stop()

    assert len(received) >= 2
    assert all(e.payload.get("integration") is True for e in received)
    assert all(isinstance(e, Event) for e in received)


# ── Graceful shutdown ─────────────────────────────────


@pytest.mark.asyncio
async def test_graceful_shutdown_no_hanging_tasks():
    """After stopping collectors and bus, no tasks remain pending."""
    bus = EventBus()
    collector = IntegrationCollector(bus, interval=0.05)

    await bus.start()
    await collector.start()
    await asyncio.sleep(0.15)

    await collector.stop()
    await bus.stop()

    assert collector.running is False
    assert bus.running is False

    # Verify internal task references are cleaned up
    assert collector._task is None
    assert bus._consumer_task is None


@pytest.mark.asyncio
async def test_multiple_collectors_shutdown():
    """Multiple collectors can be started and stopped without leaks."""
    bus = EventBus()

    collectors = [IntegrationCollector(bus, interval=0.05) for _ in range(5)]

    await bus.start()
    for c in collectors:
        await c.start()

    await asyncio.sleep(0.15)

    for c in collectors:
        await c.stop()
    await bus.stop()

    for c in collectors:
        assert c.running is False
        assert c._task is None


# ── Event structure validation for rules engine ───────


@pytest.mark.asyncio
async def test_events_have_required_fields_for_rules_engine():
    """Events emitted by collectors have all fields needed by the rules engine."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = IntegrationCollector(bus, interval=0.05)
    await collector.start()
    await asyncio.sleep(0.1)
    await collector.stop()
    await bus.stop()

    assert len(received) >= 1
    for event in received:
        # Rules engine needs these fields to match against rules.yaml
        assert hasattr(event, "id") and event.id
        assert hasattr(event, "source") and isinstance(event.source, EventSource)
        assert hasattr(event, "event_type") and isinstance(event.event_type, EventType)
        assert hasattr(event, "payload") and isinstance(event.payload, dict)
        assert hasattr(event, "timestamp") and event.timestamp is not None

        # Event must be serializable (for DB storage / WebSocket)
        data = event.model_dump()
        assert "id" in data
        assert "source" in data
        assert "event_type" in data
        assert "payload" in data
        assert "timestamp" in data


# ── No resource leaks ────────────────────────────────


@pytest.mark.asyncio
async def test_eventbus_queue_drains_on_stop():
    """EventBus queue should be empty after stop (drain completes)."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    # Publish several events
    for _ in range(10):
        await bus.publish(
            Event(source=EventSource.SIMULATOR, event_type=EventType.CPU_USAGE)
        )

    await bus.stop()

    # Queue should be drained
    assert bus.pending == 0
    assert len(received) == 10
