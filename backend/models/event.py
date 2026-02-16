from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class EventSource(StrEnum):
    PORT_COLLECTOR = "port_collector"
    PROCESS_COLLECTOR = "process_collector"
    CONNECTION_COLLECTOR = "connection_collector"
    CPU_COLLECTOR = "cpu_collector"
    FILE_COLLECTOR = "file_collector"
    LOG_COLLECTOR = "log_collector"
    SIMULATOR = "simulator"


class EventType(StrEnum):
    PORT_OPEN = "port_open"
    PROCESS_RUNNING = "process_running"
    CONNECTION_ACTIVE = "connection_active"
    CPU_USAGE = "cpu_usage"
    FILE_CHANGED = "file_changed"
    LOGIN_FAILED = "login_failed"


class Event(BaseModel):
    """Raw event emitted by a collector before rule evaluation."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: EventSource
    event_type: EventType
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
