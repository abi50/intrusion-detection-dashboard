from __future__ import annotations

import asyncio

import pytest

from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType


def _make_event(**overrides) -> Event:
    defaults = dict(
        source=EventSource.CPU_COLLECTOR,
        event_type=EventType.CPU_USAGE,
        payload={"percent": 50.0},
    )
    defaults.update(overrides)
    return Event(**defaults)


# ── publish / consume ───────────────────────────────────


@pytest.mark.asyncio
async def test_single_publish_and_consume():
    """One published event reaches one subscriber."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    event = _make_event()
    await bus.publish(event)

    # Give the consumer loop time to dispatch
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received) == 1
    assert received[0].id == event.id


@pytest.mark.asyncio
async def test_multiple_events_dispatched_in_order():
    """Events are consumed in FIFO order."""
    bus = EventBus()
    received: list[str] = []

    async def handler(event: Event) -> None:
        received.append(event.id)

    bus.subscribe(handler)
    await bus.start()

    events = [_make_event() for _ in range(5)]
    for e in events:
        await bus.publish(e)

    await asyncio.sleep(0.5)
    await bus.stop()

    assert received == [e.id for e in events]


@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    """Every subscriber gets every event."""
    bus = EventBus()
    received_a: list[Event] = []
    received_b: list[Event] = []

    async def handler_a(event: Event) -> None:
        received_a.append(event)

    async def handler_b(event: Event) -> None:
        received_b.append(event)

    bus.subscribe(handler_a)
    bus.subscribe(handler_b)
    await bus.start()

    await bus.publish(_make_event())
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received_a) == 1
    assert len(received_b) == 1
    assert received_a[0].id == received_b[0].id


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    """After unsubscribe, handler no longer receives events."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.start()

    await bus.publish(_make_event())
    await asyncio.sleep(0.2)

    bus.unsubscribe(handler)

    await bus.publish(_make_event())
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received) == 1


# ── error handling ──────────────────────────────────────


@pytest.mark.asyncio
async def test_failing_subscriber_does_not_block_others():
    """A subscriber that raises doesn't prevent other subscribers from receiving."""
    bus = EventBus()
    received: list[Event] = []

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("boom")

    async def good_handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(bad_handler)
    bus.subscribe(good_handler)
    await bus.start()

    await bus.publish(_make_event())
    await asyncio.sleep(0.2)
    await bus.stop()

    assert len(received) == 1


# ── lifecycle ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_stop_idempotent():
    """Starting/stopping multiple times doesn't raise."""
    bus = EventBus()
    await bus.start()
    await bus.start()  # double start
    assert bus.running is True

    await bus.stop()
    await bus.stop()  # double stop
    assert bus.running is False


@pytest.mark.asyncio
async def test_drain_on_stop():
    """Events already in the queue are dispatched before stop completes."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    # Don't start the consumer — put events directly into the queue
    events = [_make_event() for _ in range(3)]
    for e in events:
        await bus._queue.put(e)

    assert bus.pending == 3

    # start then immediately stop — drain should pick them up
    bus._running = True
    await bus.stop()

    assert len(received) == 3
    assert bus.pending == 0


# ── introspection ───────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_and_subscriber_count():
    bus = EventBus()

    async def noop(event: Event) -> None:
        pass

    assert bus.subscriber_count == 0
    assert bus.pending == 0

    bus.subscribe(noop)
    assert bus.subscriber_count == 1

    await bus._queue.put(_make_event())
    assert bus.pending == 1
