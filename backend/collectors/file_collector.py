from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType

logger = logging.getLogger(__name__)


class FileCollector(BaseCollector):
    """Monitors files in a directory and emits events when file hashes change."""

    name = "file_collector"

    def __init__(
        self,
        event_bus: EventBus,
        monitored_dir: str | Path,
        interval: float = 5.0,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self._monitored_dir = Path(monitored_dir)
        self._hash_cache: dict[str, str] = {}

    async def collect(self) -> list[Event]:
        events: list[Event] = []

        if not self._monitored_dir.exists():
            return events

        current_files: dict[str, str] = {}

        for path in self._monitored_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                file_hash = self._hash_file(path)
            except OSError:
                continue

            key = str(path)
            current_files[key] = file_hash

            prev_hash = self._hash_cache.get(key)
            if prev_hash is None:
                # New file — record but don't alert
                continue

            if file_hash != prev_hash:
                events.append(
                    Event(
                        source=EventSource.FILE_COLLECTOR,
                        event_type=EventType.FILE_CHANGED,
                        payload={
                            "path": key,
                            "hash_match": False,
                            "old_hash": prev_hash[:16],
                            "new_hash": file_hash[:16],
                        },
                    )
                )

        self._hash_cache = current_files
        return events

    @staticmethod
    def _hash_file(path: Path, chunk_size: int = 65536) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
