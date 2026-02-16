from __future__ import annotations

import math
from datetime import datetime, timezone

from backend.models import Alert


class RiskScorer:
    """Computes aggregate risk from active alerts using exponential time decay."""

    def __init__(
        self,
        decay_lambda: float = 0.005,
        max_score: float = 100.0,
    ) -> None:
        self.decay_lambda = decay_lambda
        self.max_score = max_score

    def compute(
        self,
        alerts: list[Alert],
        now: datetime | None = None,
    ) -> float:
        if not alerts:
            return 0.0
        if now is None:
            now = datetime.now(timezone.utc)
        total = 0.0
        for alert in alerts:
            age_seconds = (now - alert.created_at).total_seconds()
            decayed = alert.base_score * math.exp(-self.decay_lambda * age_seconds)
            total += decayed
        return min(total, self.max_score)
