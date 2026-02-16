from __future__ import annotations

import psutil

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


class PortCollector(BaseCollector):
    """Scans listening ports and emits events for ports outside the allowed set."""

    name = "port_collector"

    def __init__(
        self,
        event_bus: EventBus,
        interval: float = 5.0,
        allowed_ports: set[int] | None = None,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self.allowed_ports: set[int] = allowed_ports or {
            22, 80, 443, 3000, 5173, 8000, 8080,
        }
        self._previously_seen: set[int] = set()

    async def collect(self) -> list[Event]:
        listening = self._get_listening_ports()
        events: list[Event] = []

        for port, pid, process_name in listening:
            if port not in self.allowed_ports and port not in self._previously_seen:
                events.append(
                    Event(
                        source=EventSource.PORT_COLLECTOR,
                        event_type=EventType.PORT_OPEN,
                        payload={
                            "port": port,
                            "pid": pid,
                            "process": process_name,
                        },
                    )
                )

        # Update seen set so we only alert on first appearance
        self._previously_seen = {p for p, _, _ in listening}

        return events

    @staticmethod
    def _get_listening_ports() -> list[tuple[int, int, str]]:
        """Return (port, pid, process_name) for all LISTEN sockets."""
        results: list[tuple[int, int, str]] = []
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr:
                port = conn.laddr.port
                pid = conn.pid or 0
                try:
                    name = psutil.Process(pid).name() if pid else "unknown"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    name = "unknown"
                results.append((port, pid, name))
        return results
