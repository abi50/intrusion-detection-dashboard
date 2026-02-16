"""Tests for backend.engine.risk_scorer."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from backend.engine.risk_scorer import RiskScorer
from backend.models import Alert, Severity


def _make_alert(base_score: float, age_seconds: float, now: datetime) -> Alert:
    return Alert(
        rule_id="TEST",
        severity=Severity.HIGH,
        base_score=base_score,
        created_at=now - timedelta(seconds=age_seconds),
    )


class TestSingleAlert:
    def test_fresh_alert(self):
        scorer = RiskScorer()
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alert = _make_alert(base_score=24.0, age_seconds=0, now=now)
        score = scorer.compute([alert], now=now)
        assert score == pytest.approx(24.0)

    def test_known_decay(self):
        scorer = RiskScorer(decay_lambda=0.005)
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alert = _make_alert(base_score=24.0, age_seconds=100, now=now)
        expected = 24.0 * math.exp(-0.005 * 100)
        assert scorer.compute([alert], now=now) == pytest.approx(expected)


class TestMultipleAlerts:
    def test_sum(self):
        scorer = RiskScorer()
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        a1 = _make_alert(base_score=20.0, age_seconds=0, now=now)
        a2 = _make_alert(base_score=30.0, age_seconds=0, now=now)
        assert scorer.compute([a1, a2], now=now) == pytest.approx(50.0)

    def test_capped_at_100(self):
        scorer = RiskScorer(max_score=100.0)
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alerts = [_make_alert(base_score=40.0, age_seconds=0, now=now) for _ in range(5)]
        assert scorer.compute(alerts, now=now) == 100.0


class TestDecayBehavior:
    def test_old_alerts_near_zero(self):
        scorer = RiskScorer(decay_lambda=0.005)
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alert = _make_alert(base_score=36.0, age_seconds=3600, now=now)
        score = scorer.compute([alert], now=now)
        # e^(-0.005 * 3600) ≈ e^(-18) ≈ 1.5e-8 → near zero
        assert score < 0.001

    def test_decay_decreases_over_time(self):
        scorer = RiskScorer()
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alert = _make_alert(base_score=24.0, age_seconds=0, now=now)
        s0 = scorer.compute([alert], now=now)
        s1 = scorer.compute([alert], now=now + timedelta(seconds=60))
        s2 = scorer.compute([alert], now=now + timedelta(seconds=300))
        assert s0 > s1 > s2 > 0


class TestEmptyList:
    def test_no_alerts(self):
        scorer = RiskScorer()
        assert scorer.compute([]) == 0.0


class TestCustomParams:
    def test_custom_max_score(self):
        scorer = RiskScorer(max_score=50.0)
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alerts = [_make_alert(base_score=30.0, age_seconds=0, now=now) for _ in range(3)]
        assert scorer.compute(alerts, now=now) == 50.0

    def test_custom_decay_lambda(self):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        alert = _make_alert(base_score=10.0, age_seconds=100, now=now)
        slow = RiskScorer(decay_lambda=0.001).compute([alert], now=now)
        fast = RiskScorer(decay_lambda=0.01).compute([alert], now=now)
        assert slow > fast
