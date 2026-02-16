from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_MULTIPLIER: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class Alert(BaseModel):
    """Alert generated when an event matches a detection rule."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    rule_id: str
    severity: Severity
    base_score: float = 0.0
    message: str = ""
    source: str = ""
    payload: dict = Field(default_factory=dict)
    acknowledged: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
