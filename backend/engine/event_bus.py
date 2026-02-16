from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from backend.models.event import Event

logger = logging.getLogger(__name__)

Subscriber = Callable[[Event], Awaitable[None]]


class EventBus:
    """Central async event pipeline connecting collectors to the rules engine."""

    def __init__(self, maxsize: int = 1000) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self._subscribers: list[Subscriber] = []
        self._running = False
        self._consumer_task: asyncio.Task | None = None

    # ── lifecycle ────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        # Drain remaining events before stopping
        await self._drain()
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        logger.info("EventBus stopped")

    # ── publish / subscribe ─────────────────────────────

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    def subscribe(self, callback: Subscriber) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        self._subscribers.remove(callback)

    # ── internals ───────────────────────────────────────

    async def _consume_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(event)
            self._queue.task_done()

    async def _drain(self) -> None:
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            await self._dispatch(event)
            self._queue.task_done()

    async def _dispatch(self, event: Event) -> None:
        for sub in self._subscribers:
            try:
                await sub(event)
            except Exception:
                logger.exception("Subscriber %s failed for event %s", sub, event.id)

    # ── introspection ───────────────────────────────────

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
