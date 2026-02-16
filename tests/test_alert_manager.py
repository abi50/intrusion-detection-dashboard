"""Tests for backend.engine.alert_manager."""

from __future__ import annotations

import asyncio
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.engine.alert_manager import AlertManager
from backend.engine.risk_scorer import RiskScorer
from backend.engine.rules_engine import RulesEngine
from backend.models import Alert, Event, EventSource, EventType, Severity


# ── fixtures ───────────────────────────────────────────

RULES_YAML = """\
rules:
  - id: HIGH_CPU
    description: "CPU above 90"
    source: cpu_collector
    condition:
      field: percent
      operator: gt
      value: 90
    severity: MEDIUM
    weight: 4
"""


@pytest.fixture
def rules_path(tmp_path: Path) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(textwrap.dedent(RULES_YAML))
    return p


@pytest.fixture
def rules_engine(rules_path: Path) -> RulesEngine:
    return RulesEngine(rules_path)


@pytest.fixture
def risk_scorer() -> RiskScorer:
    return RiskScorer()


@pytest.fixture
def cpu_event() -> Event:
    return Event(
        source=EventSource.CPU_COLLECTOR,
        event_type=EventType.CPU_USAGE,
        payload={"percent": 95},
    )


@pytest.fixture
def low_cpu_event() -> Event:
    return Event(
        source=EventSource.CPU_COLLECTOR,
        event_type=EventType.CPU_USAGE,
        payload={"percent": 50},
    )


# ── tests ──────────────────────────────────────────────

class TestAlertCreation:
    @pytest.mark.asyncio
    async def test_matching_event_creates_alert(self, rules_engine, risk_scorer, cpu_event):
        callback = AsyncMock()
        manager = AlertManager(rules_engine, risk_scorer, on_alert_callback=callback)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock) as mock_insert,
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(cpu_event)
            mock_insert.assert_called_once()
            alert_arg = mock_insert.call_args[0][0]
            assert alert_arg.rule_id == "HIGH_CPU"
            assert alert_arg.base_score == 4 * 2  # weight=4, MEDIUM mult=2

    @pytest.mark.asyncio
    async def test_non_matching_event_no_alert(self, rules_engine, risk_scorer, low_cpu_event):
        manager = AlertManager(rules_engine, risk_scorer)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock) as mock_insert,
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(low_cpu_event)
            mock_insert.assert_not_called()


class TestDedup:
    @pytest.mark.asyncio
    async def test_same_event_within_cooldown_deduped(self, rules_engine, risk_scorer, cpu_event):
        manager = AlertManager(rules_engine, risk_scorer, cooldown_seconds=60.0)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock) as mock_insert,
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(cpu_event)
            await manager.handle_event(cpu_event)
            assert mock_insert.call_count == 1

    @pytest.mark.asyncio
    async def test_same_event_after_cooldown_not_deduped(self, rules_engine, risk_scorer, cpu_event):
        manager = AlertManager(rules_engine, risk_scorer, cooldown_seconds=60.0)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock) as mock_insert,
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(cpu_event)
            # Simulate cooldown expiry by backdating the cache entry
            for key in manager._dedup_cache:
                manager._dedup_cache[key] = datetime.now(timezone.utc) - timedelta(seconds=120)
            await manager.handle_event(cpu_event)
            assert mock_insert.call_count == 2


class TestRiskScoreRecalculated:
    @pytest.mark.asyncio
    async def test_risk_score_persisted(self, rules_engine, risk_scorer, cpu_event):
        manager = AlertManager(rules_engine, risk_scorer)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock),
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock) as mock_risk,
        ):
            await manager.handle_event(cpu_event)
            mock_risk.assert_called_once()


class TestCallback:
    @pytest.mark.asyncio
    async def test_callback_invoked(self, rules_engine, risk_scorer, cpu_event):
        callback = AsyncMock()
        manager = AlertManager(rules_engine, risk_scorer, on_alert_callback=callback)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock),
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(cpu_event)
            callback.assert_called_once()
            alert_arg, score_arg = callback.call_args[0]
            assert isinstance(alert_arg, Alert)
            assert isinstance(score_arg, float)

    @pytest.mark.asyncio
    async def test_no_callback_when_no_match(self, rules_engine, risk_scorer, low_cpu_event):
        callback = AsyncMock()
        manager = AlertManager(rules_engine, risk_scorer, on_alert_callback=callback)

        with (
            patch("backend.engine.alert_manager.db.insert_alert", new_callable=AsyncMock),
            patch("backend.engine.alert_manager.db.get_active_alerts", new_callable=AsyncMock, return_value=[]),
            patch("backend.engine.alert_manager.db.insert_risk_score", new_callable=AsyncMock),
        ):
            await manager.handle_event(low_cpu_event)
            callback.assert_not_called()
