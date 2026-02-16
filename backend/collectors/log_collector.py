from __future__ import annotations

import logging
import platform
import re
import time
from pathlib import Path

from backend.collectors.base import BaseCollector
from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType

logger = logging.getLogger(__name__)


class LogCollector(BaseCollector):
    """Parses authentication logs for failed login attempts.

    Cross-platform:
    - Linux: reads /var/log/auth.log (or /var/log/secure on RHEL)
    - Windows: uses win32evtlog if available, otherwise no-ops gracefully
    """

    name = "log_collector"

    def __init__(
        self,
        event_bus: EventBus,
        interval: float = 5.0,
        window_seconds: float = 60.0,
    ) -> None:
        super().__init__(event_bus, interval=interval)
        self.window_seconds = window_seconds
        self._failure_timestamps: list[float] = []
        self._last_position: int = 0
        self._log_path: Path | None = self._find_log_path()

    async def collect(self) -> list[Event]:
        new_failures = self._read_failures()
        now = time.time()

        self._failure_timestamps.extend(new_failures)

        # Prune old entries outside the window
        cutoff = now - self.window_seconds
        self._failure_timestamps = [
            t for t in self._failure_timestamps if t > cutoff
        ]

        count = len(self._failure_timestamps)
        if count == 0:
            return []

        return [
            Event(
                source=EventSource.LOG_COLLECTOR,
                event_type=EventType.LOGIN_FAILED,
                payload={
                    "failed_logins": count,
                    "window_seconds": self.window_seconds,
                },
            )
        ]

    def _read_failures(self) -> list[float]:
        """Read new failed login lines from the auth log. Returns timestamps."""
        if platform.system() == "Windows":
            return self._read_windows_failures()
        return self._read_linux_failures()

    def _read_linux_failures(self) -> list[float]:
        if not self._log_path or not self._log_path.exists():
            return []

        failures: list[float] = []
        now = time.time()

        try:
            with open(self._log_path, "r", errors="replace") as f:
                f.seek(self._last_position)
                for line in f:
                    lower = line.lower()
                    if any(pat in lower for pat in (
                        "authentication failure",
                        "failed password",
                        "invalid user",
                        "failed login",
                    )):
                        failures.append(now)
                self._last_position = f.tell()
        except OSError:
            logger.debug("Cannot read auth log: %s", self._log_path)

        return failures

    def _read_windows_failures(self) -> list[float]:
        """Read Windows Security event log for failed logins (event ID 4625)."""
        try:
            import win32evtlog  # type: ignore[import-not-found]
            import win32con  # type: ignore[import-not-found]
        except ImportError:
            return []

        failures: list[float] = []
        now = time.time()

        try:
            hand = win32evtlog.OpenEventLog(None, "Security")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            events = win32evtlog.ReadEventLog(hand, flags, 0)
            for event in events:
                if event.EventID & 0xFFFF == 4625:
                    event_time = event.TimeGenerated.timestamp()
                    if event_time > now - self.window_seconds:
                        failures.append(event_time)
            win32evtlog.CloseEventLog(hand)
        except Exception:
            logger.debug("Cannot read Windows Security log", exc_info=True)

        return failures

    @staticmethod
    def _find_log_path() -> Path | None:
        if platform.system() == "Windows":
            return None
        for p in ("/var/log/auth.log", "/var/log/secure"):
            path = Path(p)
            if path.exists():
                return path
        return None
