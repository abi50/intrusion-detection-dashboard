from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from backend.engine.event_bus import EventBus
from backend.models.event import Event

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Abstract base for all system collectors.

    Subclasses implement ``collect()`` which returns a list of events.
    The base class handles the async loop, interval timing, and graceful shutdown.
    """

    name: str = "base"
    interval: float = 5.0  # seconds between collections

    def __init__(self, event_bus: EventBus, interval: float | None = None) -> None:
        self._event_bus = event_bus
        if interval is not None:
            self.interval = interval
        self._running = False
        self._task: asyncio.Task | None = None

    # ── lifecycle ────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Collector [%s] started (interval=%.1fs)", self.name, self.interval)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Collector [%s] stopped", self.name)

    # ── abstract method ─────────────────────────────────

    @abstractmethod
    async def collect(self) -> list[Event]:
        """Gather system data and return events to publish."""
        ...

    # ── internals ───────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                events = await self.collect()
                for event in events:
                    await self._event_bus.publish(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Collector [%s] error during collect()", self.name)
            await asyncio.sleep(self.interval)

    @property
    def running(self) -> bool:
        return self._running
