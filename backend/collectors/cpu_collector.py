from __future__ import annotations

import time

import psutil

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


class CpuCollector(BaseCollector):
    """Monitors CPU usage and emits events when thresholds are crossed.

    Tracks sustained spikes: only emits an event when CPU stays above
    ``spike_threshold`` for ``sustained_seconds`` continuously.
    """

    name = "cpu_collector"

    def __init__(
        self,
        event_bus: EventBus,
        interval: float = 5.0,
        spike_threshold: float = 90.0,
        sustained_seconds: float = 30.0,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self.spike_threshold = spike_threshold
        self.sustained_seconds = sustained_seconds
        self._spike_start: float | None = None

    async def collect(self) -> list[Event]:
        cpu_percent = psutil.cpu_percent(interval=0)
        now = time.monotonic()
        events: list[Event] = []

        # Always emit a reading event for metrics
        events.append(
            Event(
                source=EventSource.CPU_COLLECTOR,
                event_type=EventType.CPU_USAGE,
                payload={"percent": cpu_percent, "sustained": False},
            )
        )

        # Track sustained spike
        if cpu_percent >= self.spike_threshold:
            if self._spike_start is None:
                self._spike_start = now
            elif (now - self._spike_start) >= self.sustained_seconds:
                duration = round(now - self._spike_start, 1)
                events.append(
                    Event(
                        source=EventSource.CPU_COLLECTOR,
                        event_type=EventType.CPU_USAGE,
                        payload={
                            "percent": cpu_percent,
                            "sustained": True,
                            "duration_seconds": duration,
                        },
                    )
                )
        else:
            self._spike_start = None

        return events
