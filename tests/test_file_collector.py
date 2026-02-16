"""Tests for backend.collectors.file_collector."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.collectors.file_collector import FileCollector
from backend.engine.event_bus import EventBus
from backend.models.event import EventSource, EventType


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def monitored_dir(tmp_path: Path) -> Path:
    d = tmp_path / "monitored"
    d.mkdir()
    return d


@pytest.fixture
def collector(event_bus, monitored_dir):
    return FileCollector(event_bus, monitored_dir=monitored_dir, interval=1.0)


class TestFileCollector:
    @pytest.mark.asyncio
    async def test_no_events_on_first_scan(self, collector, monitored_dir):
        (monitored_dir / "file.txt").write_text("hello")
        events = await collector.collect()
        assert events == []  # first scan just records hashes

    @pytest.mark.asyncio
    async def test_detects_file_change(self, collector, monitored_dir):
        f = monitored_dir / "file.txt"
        f.write_text("original")
        await collector.collect()  # first scan

        f.write_text("modified")
        events = await collector.collect()
        assert len(events) == 1
        assert events[0].source == EventSource.FILE_COLLECTOR
        assert events[0].event_type == EventType.FILE_CHANGED
        assert events[0].payload["hash_match"] is False

    @pytest.mark.asyncio
    async def test_no_event_when_unchanged(self, collector, monitored_dir):
        f = monitored_dir / "file.txt"
        f.write_text("stable")
        await collector.collect()  # first scan
        events = await collector.collect()  # second scan, no change
        assert events == []

    @pytest.mark.asyncio
    async def test_payload_contains_path_and_hashes(self, collector, monitored_dir):
        f = monitored_dir / "config.yaml"
        f.write_text("key: value")
        await collector.collect()

        f.write_text("key: changed")
        events = await collector.collect()
        p = events[0].payload
        assert "path" in p
        assert "old_hash" in p
        assert "new_hash" in p
        assert p["old_hash"] != p["new_hash"]

    @pytest.mark.asyncio
    async def test_new_file_not_alerted(self, collector, monitored_dir):
        (monitored_dir / "a.txt").write_text("aaa")
        await collector.collect()

        # Add a new file on the second scan
        (monitored_dir / "b.txt").write_text("bbb")
        events = await collector.collect()
        assert events == []  # new file recorded, not alerted

    @pytest.mark.asyncio
    async def test_multiple_files_changed(self, collector, monitored_dir):
        f1 = monitored_dir / "one.txt"
        f2 = monitored_dir / "two.txt"
        f1.write_text("1")
        f2.write_text("2")
        await collector.collect()

        f1.write_text("1-changed")
        f2.write_text("2-changed")
        events = await collector.collect()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_empty_directory(self, collector):
        events = await collector.collect()
        assert events == []

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, event_bus, tmp_path):
        collector = FileCollector(event_bus, monitored_dir=tmp_path / "nope", interval=1.0)
        events = await collector.collect()
        assert events == []

    @pytest.mark.asyncio
    async def test_subdirectory_files_monitored(self, collector, monitored_dir):
        sub = monitored_dir / "subdir"
        sub.mkdir()
        f = sub / "deep.txt"
        f.write_text("deep content")
        await collector.collect()

        f.write_text("deep changed")
        events = await collector.collect()
        assert len(events) == 1
