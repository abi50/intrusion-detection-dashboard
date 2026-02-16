from __future__ import annotations

import asyncio
from collections import namedtuple
from unittest.mock import patch, MagicMock

import pytest

from backend.collectors.port_collector import PortCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event


# Helper to build fake psutil connection objects
FakeAddr = namedtuple("FakeAddr", ["ip", "port"])
FakeConn = namedtuple("FakeConn", ["laddr", "raddr", "status", "pid"])


def _conn(port: int, pid: int = 1000, status: str = "LISTEN") -> FakeConn:
    return FakeConn(
        laddr=FakeAddr("0.0.0.0", port),
        raddr=None,
        status=status,
        pid=pid,
    )


def _patch_ports(connections: list[FakeConn], process_name: str = "test.exe"):
    """Context manager to mock psutil.net_connections and psutil.Process."""
    mock_psutil = MagicMock()
    mock_psutil.net_connections.return_value = connections
    mock_psutil.CONN_LISTEN = "LISTEN"
    mock_process = MagicMock()
    mock_process.name.return_value = process_name
    mock_psutil.Process.return_value = mock_process
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = Exception
    return patch("backend.collectors.port_collector.psutil", mock_psutil)


# ── detection ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_detects_suspicious_port():
    """Ports outside allowed set produce an alert event."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports={80, 443})

    with _patch_ports([_conn(4444)]):
        events = await collector.collect()

    assert len(events) == 1
    assert events[0].payload["port"] == 4444
    assert events[0].payload["process"] == "test.exe"


@pytest.mark.asyncio
async def test_ignores_allowed_ports():
    """Ports in the allowed set produce no events."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports={80, 443, 8000})

    with _patch_ports([_conn(80), _conn(443), _conn(8000)]):
        events = await collector.collect()

    assert len(events) == 0


@pytest.mark.asyncio
async def test_mixed_ports():
    """Only suspicious ports produce events."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports={80})

    with _patch_ports([_conn(80), _conn(4444), _conn(9999)]):
        events = await collector.collect()

    ports = {e.payload["port"] for e in events}
    assert ports == {4444, 9999}


# ── deduplication ───────────────────────────────────────


@pytest.mark.asyncio
async def test_only_alerts_on_first_appearance():
    """Same suspicious port on consecutive cycles only triggers once."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports={80})

    with _patch_ports([_conn(4444)]):
        events_1 = await collector.collect()
        events_2 = await collector.collect()

    assert len(events_1) == 1
    assert len(events_2) == 0  # already seen


@pytest.mark.asyncio
async def test_alerts_again_after_port_disappears_and_returns():
    """If a suspicious port closes then re-opens, we alert again."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports={80})

    with _patch_ports([_conn(4444)]):
        events_1 = await collector.collect()

    # Port disappears
    with _patch_ports([]):
        await collector.collect()

    # Port re-appears
    with _patch_ports([_conn(4444)]):
        events_3 = await collector.collect()

    assert len(events_1) == 1
    assert len(events_3) == 1


# ── ignores non-LISTEN ──────────────────────────────────


@pytest.mark.asyncio
async def test_ignores_non_listen_connections():
    """ESTABLISHED and other non-LISTEN connections are ignored."""
    bus = EventBus()
    collector = PortCollector(bus, allowed_ports=set())

    connections = [
        _conn(4444, status="LISTEN"),
        _conn(5555, status="ESTABLISHED"),
        _conn(6666, status="TIME_WAIT"),
    ]
    with _patch_ports(connections):
        events = await collector.collect()

    assert len(events) == 1
    assert events[0].payload["port"] == 4444


# ── end to end ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_to_end_with_bus():
    """PortCollector publishes events through the EventBus."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    collector = PortCollector(bus, interval=0.1, allowed_ports={80})

    with _patch_ports([_conn(4444), _conn(80)]):
        await collector.start()
        await asyncio.sleep(0.25)
        await collector.stop()

    await bus.stop()

    # First cycle emits 1 event (port 4444), subsequent cycles emit 0 (dedup)
    assert len(received) == 1
    assert received[0].payload["port"] == 4444
