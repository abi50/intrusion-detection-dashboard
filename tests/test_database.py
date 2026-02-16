"""Tests for backend.db.database — async SQLite operations.

Every test uses an in-memory or temp-file database so tests are
deterministic and don't touch real system state.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.models.alert import Alert, Severity
from backend.models.metrics import SystemMetrics


# ── helpers ────────────────────────────────────────────

def _tmp_db_path(tmp_path: Path) -> str:
    """Return a fresh SQLite path inside pytest's tmp_path."""
    return str(tmp_path / "test_ids.db")


def _make_alert(**overrides) -> Alert:
    defaults = dict(
        rule_id="TEST_RULE",
        severity=Severity.HIGH,
        base_score=24.0,
        message="test alert",
        source="test_source",
        payload={"key": "value"},
    )
    defaults.update(overrides)
    return Alert(**defaults)


# ── fixtures ──────────────────────────────────────────


@pytest.fixture()
def db_path(tmp_path):
    """Provide a temp DB path and patch settings.db_path."""
    path = _tmp_db_path(tmp_path)
    with patch("backend.db.database.settings") as mock_settings:
        mock_settings.db_path = path
        yield path


@pytest.fixture()
async def db(db_path):
    """Initialize the DB schema so tables exist."""
    from backend.db.database import init_db
    await init_db()
    yield db_path


# ── init_db ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_db_creates_tables(db):
    import aiosqlite

    async with aiosqlite.connect(db) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()}

    assert "alerts" in tables
    assert "events" in tables
    assert "metrics_history" in tables
    assert "risk_history" in tables


@pytest.mark.asyncio
async def test_init_db_is_idempotent(db):
    """Calling init_db twice should not raise."""
    from backend.db.database import init_db
    await init_db()  # second call


# ── alert CRUD ────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_and_get_alert(db):
    from backend.db.database import insert_alert, get_alert_by_id

    alert = _make_alert()
    await insert_alert(alert)

    row = await get_alert_by_id(alert.id)
    assert row is not None
    assert row["rule_id"] == "TEST_RULE"
    assert row["severity"] == "HIGH"
    assert row["base_score"] == 24.0
    assert row["payload"] == {"key": "value"}
    assert row["acknowledged"] is False


@pytest.mark.asyncio
async def test_get_alerts_returns_list(db):
    from backend.db.database import insert_alert, get_alerts

    for i in range(3):
        await insert_alert(_make_alert(message=f"alert-{i}"))

    rows = await get_alerts()
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_get_alerts_filter_by_severity(db):
    from backend.db.database import insert_alert, get_alerts

    await insert_alert(_make_alert(severity=Severity.HIGH))
    await insert_alert(_make_alert(severity=Severity.LOW))

    rows = await get_alerts(severity="HIGH")
    assert len(rows) == 1
    assert rows[0]["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_get_alerts_pagination(db):
    from backend.db.database import insert_alert, get_alerts

    for i in range(5):
        await insert_alert(_make_alert(message=f"a-{i}"))

    page1 = await get_alerts(limit=2, offset=0)
    page2 = await get_alerts(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0]["id"] != page2[0]["id"]


@pytest.mark.asyncio
async def test_acknowledge_alert(db):
    from backend.db.database import insert_alert, acknowledge_alert, get_alert_by_id

    alert = _make_alert()
    await insert_alert(alert)

    result = await acknowledge_alert(alert.id)
    assert result is True

    row = await get_alert_by_id(alert.id)
    assert row["acknowledged"] is True


@pytest.mark.asyncio
async def test_acknowledge_nonexistent_returns_false(db):
    from backend.db.database import acknowledge_alert

    result = await acknowledge_alert("nonexistent_id")
    assert result is False


@pytest.mark.asyncio
async def test_get_active_alerts_excludes_acknowledged(db):
    from backend.db.database import insert_alert, acknowledge_alert, get_active_alerts

    a1 = _make_alert()
    a2 = _make_alert()
    await insert_alert(a1)
    await insert_alert(a2)

    await acknowledge_alert(a1.id)

    active = await get_active_alerts()
    assert len(active) == 1
    assert active[0]["id"] == a2.id


@pytest.mark.asyncio
async def test_get_alert_by_id_nonexistent(db):
    from backend.db.database import get_alert_by_id

    row = await get_alert_by_id("does_not_exist")
    assert row is None


# ── metrics ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_and_get_metrics(db):
    from backend.db.database import insert_metrics, get_metrics_history

    m = SystemMetrics(
        cpu_percent=65.0,
        memory_percent=40.0,
        open_ports=5,
        active_connections=10,
        process_count=200,
    )
    await insert_metrics(m)

    rows = await get_metrics_history(minutes=1)
    assert len(rows) == 1
    assert rows[0]["cpu_percent"] == 65.0
    assert rows[0]["process_count"] == 200


# ── risk history ──────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_and_get_risk_score(db):
    from backend.db.database import insert_risk_score, get_risk_history

    await insert_risk_score(42.5)
    await insert_risk_score(55.0)

    rows = await get_risk_history(limit=10)
    assert len(rows) == 2
    scores = {r["score"] for r in rows}
    assert 42.5 in scores
    assert 55.0 in scores


# ── _row_to_dict helper ──────────────────────────────


def test_row_to_dict_parses_payload():
    from backend.db.database import _row_to_dict

    class FakeRow:
        """Minimal Row-like object that supports dict()."""
        def __init__(self, data):
            self._data = data
        def keys(self):
            return self._data.keys()
        def __iter__(self):
            return iter(self._data.values())
        def __getitem__(self, key):
            return self._data[key]

    row = FakeRow({"id": "abc", "payload": '{"x": 1}', "acknowledged": 1})
    d = _row_to_dict(row)
    assert d["payload"] == {"x": 1}
    assert d["acknowledged"] is True


def test_row_to_dict_no_payload():
    from backend.db.database import _row_to_dict

    class FakeRow:
        def __init__(self, data):
            self._data = data
        def keys(self):
            return self._data.keys()
        def __iter__(self):
            return iter(self._data.values())
        def __getitem__(self, key):
            return self._data[key]

    row = FakeRow({"id": "abc", "score": 42.0})
    d = _row_to_dict(row)
    assert d["score"] == 42.0
    assert "payload" not in d
