from __future__ import annotations

import psutil

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


class ProcessCollector(BaseCollector):
    """Scans running processes and emits events for suspicious process names."""

    name = "process_collector"

    def __init__(
        self,
        event_bus: EventBus,
        interval: float = 5.0,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self._previously_seen: set[int] = set()

    async def collect(self) -> list[Event]:
        events: list[Event] = []
        current_pids: set[int] = set()

        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                info = proc.info
                pid = info["pid"]
                name = (info["name"] or "").lower()
                username = info.get("username") or ""
                current_pids.add(pid)

                # Only alert on newly-seen processes
                if pid in self._previously_seen:
                    continue

                events.append(
                    Event(
                        source=EventSource.PROCESS_COLLECTOR,
                        event_type=EventType.PROCESS_RUNNING,
                        payload={
                            "name": name,
                            "pid": pid,
                            "username": username,
                        },
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self._previously_seen = current_pids
        return events
