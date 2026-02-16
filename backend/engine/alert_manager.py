from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from backend.db import database as db
from backend.models import Alert, Event, Severity
from backend.engine.rules_engine import RulesEngine
from backend.engine.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)


class AlertManager:
    """Glues rules engine + risk scorer + DB. Subscribes to EventBus."""

    def __init__(
        self,
        rules_engine: RulesEngine,
        risk_scorer: RiskScorer,
        on_alert_callback: Callable[[Alert, float], Awaitable[None]] | None = None,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.rules_engine = rules_engine
        self.risk_scorer = risk_scorer
        self.on_alert_callback = on_alert_callback
        self.cooldown_seconds = cooldown_seconds
        self._dedup_cache: dict[str, datetime] = {}

    async def handle_event(self, event: Event) -> None:
        """EventBus subscriber — evaluate event, dedup, persist, score."""
        alerts = self.rules_engine.evaluate(event)
        now = datetime.now(timezone.utc)

        for alert in alerts:
            key = self._dedup_key(alert)
            last_seen = self._dedup_cache.get(key)
            if last_seen and (now - last_seen).total_seconds() < self.cooldown_seconds:
                logger.debug("Dedup suppressed alert %s (key=%s)", alert.rule_id, key)
                continue

            self._dedup_cache[key] = now
            await db.insert_alert(alert)

            active_rows = await db.get_active_alerts()
            active_alerts = [self._row_to_alert(r) for r in active_rows]
            risk_score = self.risk_scorer.compute(active_alerts, now)
            await db.insert_risk_score(risk_score)

            if self.on_alert_callback:
                await self.on_alert_callback(alert, risk_score)

    @staticmethod
    def _dedup_key(alert: Alert) -> str:
        raw = json.dumps(
            {"rule_id": alert.rule_id, "payload": sorted(alert.payload.items())},
            default=str,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _row_to_alert(row: dict) -> Alert:
        severity = row["severity"]
        if isinstance(severity, str):
            severity = Severity(severity)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return Alert(
            id=row["id"],
            rule_id=row["rule_id"],
            severity=severity,
            base_score=row["base_score"],
            message=row.get("message", ""),
            source=row.get("source", ""),
            payload=row.get("payload", {}),
            acknowledged=row.get("acknowledged", False),
            created_at=created_at,
        )
