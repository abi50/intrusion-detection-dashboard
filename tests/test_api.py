"""Tests for backend.api routes and WebSocket."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.db import database as db
from backend.engine import EventBus, RiskScorer, RulesEngine
from backend.main import app
from backend.models import Alert, Severity


# ── fixtures ───────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _setup_db(tmp_path):
    """Use a temp DB for every test so tests don't interfere."""
    test_db = str(tmp_path / "test.db")
    with patch("backend.db.database.settings") as mock_settings:
        mock_settings.db_path = test_db
        await db.init_db()
        yield


@pytest.fixture
def _setup_app_state():
    """Inject minimal app.state so routes work without full lifespan."""
    event_bus = EventBus()
    rules_engine = RulesEngine.__new__(RulesEngine)
    rules_engine.rules = []
    rules_engine.blocklist = []

    app.state.event_bus = event_bus
    app.state.rules_engine = rules_engine
    app.state.risk_scorer = RiskScorer()
    app.state.collectors = []
    yield
    # Cleanup
    del app.state.event_bus
    del app.state.rules_engine
    del app.state.risk_scorer
    del app.state.collectors


@pytest.fixture
async def client(_setup_app_state):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── REST tests ─────────────────────────────────────────


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_ok(self, client: AsyncClient):
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "event_bus_running" in data
        assert "subscribers" in data
        assert "pending_events" in data
        assert "collectors" in data


class TestAlerts:
    @pytest.mark.asyncio
    async def test_get_alerts_empty(self, client: AsyncClient):
        resp = await client.get("/api/alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get("/api/alerts/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self, client: AsyncClient):
        resp = await client.post("/api/alerts/nonexistent/acknowledge")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_crud_alert(self, client: AsyncClient):
        # Seed an alert
        alert = Alert(
            id="test123",
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            base_score=24.0,
            message="Test alert",
            source="cpu_collector",
        )
        await db.insert_alert(alert)

        # GET list
        resp = await client.get("/api/alerts")
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) == 1
        assert alerts[0]["rule_id"] == "TEST_RULE"

        # GET single
        resp = await client.get("/api/alerts/test123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "test123"

        # Acknowledge
        resp = await client.post("/api/alerts/test123/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["acknowledged"] is True


class TestMetrics:
    @pytest.mark.asyncio
    async def test_get_metrics_empty(self, client: AsyncClient):
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200
        assert resp.json() == []


class TestRisk:
    @pytest.mark.asyncio
    async def test_get_risk_empty(self, client: AsyncClient):
        resp = await client.get("/api/risk")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_risk_with_data(self, client: AsyncClient):
        await db.insert_risk_score(42.5)
        resp = await client.get("/api/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 42.5


class TestRules:
    @pytest.mark.asyncio
    async def test_get_rules(self, client: AsyncClient):
        resp = await client.get("/api/rules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
