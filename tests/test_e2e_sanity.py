"""End-to-end runtime sanity check.

Starts EventBus, initializes collectors, emits sample events,
confirms events flow correctly and are structured for rules engine.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock
from collections import namedtuple

import pytest

from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType
from backend.collectors.cpu_collector import CpuCollector
from backend.collectors.port_collector import PortCollector


sconn = namedtuple("sconn", ["fd", "family", "type", "laddr", "raddr", "status", "pid"])
saddr = namedtuple("saddr", ["ip", "port"])


@pytest.mark.asyncio
async def test_full_pipeline_cpu_collector():
    """CPU collector → EventBus → subscriber, events are rules-engine ready."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    with patch("backend.collectors.cpu_collector.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 50.0

        collector = CpuCollector(bus, interval=0.05)
        await collector.start()
        await asyncio.sleep(0.2)
        await collector.stop()

    await bus.stop()

    assert len(received) >= 2
    for event in received:
        assert event.source == EventSource.CPU_COLLECTOR
        assert event.event_type == EventType.CPU_USAGE
        assert "percent" in event.payload
        assert isinstance(event.payload["percent"], float)
        # Rules engine compatibility: event_type matches rules.yaml CPU_SPIKE condition
        assert event.event_type.value == "cpu_usage"


@pytest.mark.asyncio
async def test_full_pipeline_port_collector():
    """Port collector → EventBus → subscriber, suspicious port detected."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    suspicious_conn = sconn(
        fd=-1, family=2, type=1,
        laddr=saddr("0.0.0.0", 4444),
        raddr=(), status="LISTEN", pid=999,
    )

    with patch("backend.collectors.port_collector.psutil") as mock_psutil:
        mock_psutil.CONN_LISTEN = "LISTEN"
        mock_proc = MagicMock()
        mock_proc.name.return_value = "suspicious.exe"
        mock_psutil.net_connections.return_value = [suspicious_conn]
        mock_psutil.Process.return_value = mock_proc

        collector = PortCollector(bus, interval=0.05)
        await collector.start()
        await asyncio.sleep(0.15)
        await collector.stop()

    await bus.stop()

    assert len(received) >= 1
    port_event = received[0]
    assert port_event.source == EventSource.PORT_COLLECTOR
    assert port_event.event_type == EventType.PORT_OPEN
    assert port_event.payload["port"] == 4444
    # Rules engine compatibility: event_type matches rules.yaml PORT_SUSPICIOUS condition
    assert port_event.event_type.value == "port_open"


@pytest.mark.asyncio
async def test_multiple_collectors_concurrent():
    """Multiple collectors run simultaneously, all events reach subscriber."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    with patch("backend.collectors.cpu_collector.psutil") as mock_cpu_psutil:
        mock_cpu_psutil.cpu_percent.return_value = 30.0

        with patch("backend.collectors.port_collector.psutil") as mock_port_psutil:
            mock_port_psutil.net_connections.return_value = []

            cpu = CpuCollector(bus, interval=0.05)
            port = PortCollector(bus, interval=0.05)

            await cpu.start()
            await port.start()
            await asyncio.sleep(0.2)
            await cpu.stop()
            await port.stop()

    await bus.stop()

    # CPU collector should have emitted readings
    cpu_events = [e for e in received if e.source == EventSource.CPU_COLLECTOR]
    assert len(cpu_events) >= 2

    # All events must be valid Event instances
    for event in received:
        assert isinstance(event, Event)
        data = event.model_dump()
        assert all(k in data for k in ("id", "source", "event_type", "payload", "timestamp"))


@pytest.mark.asyncio
async def test_manual_event_through_bus():
    """Manually published events flow through the bus correctly."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    # Simulate events that the rules engine would process
    sample_events = [
        Event(
            source=EventSource.SIMULATOR,
            event_type=EventType.PORT_OPEN,
            payload={"port": 31337, "pid": 1234, "process_name": "nc.exe"},
        ),
        Event(
            source=EventSource.SIMULATOR,
            event_type=EventType.LOGIN_FAILED,
            payload={"user": "admin", "source_ip": "192.168.1.100"},
        ),
        Event(
            source=EventSource.SIMULATOR,
            event_type=EventType.FILE_CHANGED,
            payload={"path": "/etc/passwd", "hash_before": "abc", "hash_after": "def"},
        ),
        Event(
            source=EventSource.SIMULATOR,
            event_type=EventType.CONNECTION_ACTIVE,
            payload={"remote_ip": "198.51.100.5", "remote_port": 443},
        ),
    ]

    for event in sample_events:
        await bus.publish(event)

    # Give consumer time to process
    await asyncio.sleep(0.3)
    await bus.stop()

    assert len(received) == 4

    # Verify each event type was received
    received_types = {e.event_type for e in received}
    assert EventType.PORT_OPEN in received_types
    assert EventType.LOGIN_FAILED in received_types
    assert EventType.FILE_CHANGED in received_types
    assert EventType.CONNECTION_ACTIVE in received_types

    # All events should be serializable for rules engine / DB
    for event in received:
        data = event.model_dump()
        assert isinstance(data["payload"], dict)
        assert isinstance(data["source"], str)
        assert isinstance(data["event_type"], str)
