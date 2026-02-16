from __future__ import annotations

import psutil

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


class ConnectionCollector(BaseCollector):
    """Monitors active network connections and emits events for each remote IP."""

    name = "connection_collector"

    def __init__(
        self,
        event_bus: EventBus,
        interval: float = 5.0,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self._previously_seen: set[str] = set()

    async def collect(self) -> list[Event]:
        events: list[Event] = []
        current_connections: set[str] = set()

        for conn in psutil.net_connections(kind="inet"):
            if conn.status != "ESTABLISHED" or not conn.raddr:
                continue

            remote_ip = conn.raddr.ip
            remote_port = conn.raddr.port
            local_port = conn.laddr.port if conn.laddr else 0
            pid = conn.pid or 0

            # Dedupe key: remote_ip (alert once per unique IP per cycle)
            key = remote_ip
            if key in current_connections:
                continue
            current_connections.add(key)

            # Only alert on newly-seen remote IPs
            if key in self._previously_seen:
                continue

            try:
                proc_name = psutil.Process(pid).name() if pid else "unknown"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_name = "unknown"

            events.append(
                Event(
                    source=EventSource.CONNECTION_COLLECTOR,
                    event_type=EventType.CONNECTION_ACTIVE,
                    payload={
                        "remote_ip": remote_ip,
                        "remote_port": remote_port,
                        "local_port": local_port,
                        "pid": pid,
                        "process": proc_name,
                    },
                )
            )

        self._previously_seen = current_connections
        return events
