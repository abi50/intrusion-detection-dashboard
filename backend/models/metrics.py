from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SystemMetrics(BaseModel):
    """Point-in-time snapshot of local system health."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    open_ports: int = 0
    active_connections: int = 0
    process_count: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
