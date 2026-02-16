"""Tests for backend.collectors.connection_collector."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from backend.collectors.connection_collector import ConnectionCollector
from backend.engine.event_bus import EventBus
from backend.models.event import EventSource, EventType

Addr = namedtuple("Addr", ["ip", "port"])


def _mock_conn(status: str, raddr=None, laddr=None, pid=0):
    conn = MagicMock()
    conn.status = status
    conn.raddr = raddr
    conn.laddr = laddr
    conn.pid = pid
    return conn


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def collector(event_bus):
    return ConnectionCollector(event_bus, interval=1.0)


class TestConnectionCollector:
    @pytest.mark.asyncio
    async def test_emits_event_for_established_connection(self, collector):
        conns = [
            _mock_conn("ESTABLISHED", raddr=Addr("10.66.66.5", 443), laddr=Addr("192.168.1.2", 54321), pid=100),
        ]
        with patch("backend.collectors.connection_collector.psutil.net_connections", return_value=conns), \
             patch("backend.collectors.connection_collector.psutil.Process") as mock_proc:
            mock_proc.return_value.name.return_value = "chrome"
            events = await collector.collect()

        assert len(events) == 1
        assert events[0].source == EventSource.CONNECTION_COLLECTOR
        assert events[0].event_type == EventType.CONNECTION_ACTIVE
        assert events[0].payload["remote_ip"] == "10.66.66.5"
        assert events[0].payload["process"] == "chrome"

    @pytest.mark.asyncio
    async def test_ignores_non_established(self, collector):
        conns = [
            _mock_conn("LISTEN", raddr=None, laddr=Addr("0.0.0.0", 80)),
            _mock_conn("TIME_WAIT", raddr=Addr("1.2.3.4", 80), laddr=Addr("192.168.1.2", 54321)),
        ]
        with patch("backend.collectors.connection_collector.psutil.net_connections", return_value=conns):
            events = await collector.collect()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_deduplicates_same_ip_in_cycle(self, collector):
        conns = [
            _mock_conn("ESTABLISHED", raddr=Addr("10.0.0.1", 443), laddr=Addr("192.168.1.2", 1111), pid=0),
            _mock_conn("ESTABLISHED", raddr=Addr("10.0.0.1", 80), laddr=Addr("192.168.1.2", 2222), pid=0),
        ]
        with patch("backend.collectors.connection_collector.psutil.net_connections", return_value=conns):
            events = await collector.collect()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_only_alerts_on_new_ips(self, collector):
        conns = [
            _mock_conn("ESTABLISHED", raddr=Addr("10.0.0.1", 443), laddr=Addr("192.168.1.2", 1111), pid=0),
        ]
        with patch("backend.collectors.connection_collector.psutil.net_connections", return_value=conns):
            events1 = await collector.collect()
            events2 = await collector.collect()
        assert len(events1) == 1
        assert len(events2) == 0

    @pytest.mark.asyncio
    async def test_alerts_again_after_ip_disappears(self, collector):
        conn_a = [_mock_conn("ESTABLISHED", raddr=Addr("10.0.0.1", 443), laddr=Addr("192.168.1.2", 1111), pid=0)]
        conn_b = [_mock_conn("ESTABLISHED", raddr=Addr("10.0.0.2", 80), laddr=Addr("192.168.1.2", 2222), pid=0)]

        with patch("backend.collectors.connection_collector.psutil.net_connections") as mock_net:
            mock_net.return_value = conn_a
            await collector.collect()

            mock_net.return_value = conn_b
            await collector.collect()

            # 10.0.0.1 returns after being gone
            mock_net.return_value = conn_a
            events = await collector.collect()
        assert len(events) == 1
        assert events[0].payload["remote_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_payload_fields(self, collector):
        conns = [
            _mock_conn("ESTABLISHED", raddr=Addr("8.8.8.8", 53), laddr=Addr("192.168.1.2", 45678), pid=200),
        ]
        with patch("backend.collectors.connection_collector.psutil.net_connections", return_value=conns), \
             patch("backend.collectors.connection_collector.psutil.Process") as mock_proc:
            mock_proc.return_value.name.return_value = "dns_client"
            events = await collector.collect()

        p = events[0].payload
        assert p["remote_ip"] == "8.8.8.8"
        assert p["remote_port"] == 53
        assert p["local_port"] == 45678
        assert p["pid"] == 200
        assert p["process"] == "dns_client"
