from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import aiosqlite

from backend.config import settings
from backend.models import Alert, SystemMetrics

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def get_connection() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    """Create tables if they don't exist."""
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text()
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(schema)
        await db.commit()


# ── alerts ──────────────────────────────────────────────

async def insert_alert(alert: Alert) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT INTO alerts
               (id, rule_id, severity, base_score, message, source, payload, acknowledged, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.id,
                alert.rule_id,
                alert.severity.value,
                alert.base_score,
                alert.message,
                alert.source,
                json.dumps(alert.payload),
                int(alert.acknowledged),
                alert.created_at.isoformat(),
            ),
        )
        await db.commit()


async def get_alerts(
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = "SELECT * FROM alerts"
    params: list = []
    if severity:
        query += " WHERE severity = ?"
        params.append(severity)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def get_alert_by_id(alert_id: str) -> dict | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def acknowledge_alert(alert_id: str) -> bool:
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_active_alerts() -> list[dict]:
    """Return non-acknowledged alerts for risk score calculation."""
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ── metrics ─────────────────────────────────────────────

async def insert_metrics(m: SystemMetrics) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT INTO metrics_history
               (cpu_percent, memory_percent, open_ports, active_connections, process_count, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                m.cpu_percent,
                m.memory_percent,
                m.open_ports,
                m.active_connections,
                m.process_count,
                m.timestamp.isoformat(),
            ),
        )
        await db.commit()


async def get_metrics_history(minutes: int = 30) -> list[dict]:
    cutoff = datetime.utcnow().isoformat()  # simplified — works for recent window
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM metrics_history
               ORDER BY timestamp DESC
               LIMIT ?""",
            (minutes * 12,),  # ~12 rows per minute at 5s intervals
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ── risk history ────────────────────────────────────────

async def insert_risk_score(score: float) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO risk_history (score, timestamp) VALUES (?, ?)",
            (score, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def get_risk_history(limit: int = 360) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM risk_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ── helpers ─────────────────────────────────────────────

def _row_to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    if "payload" in d and isinstance(d["payload"], str):
        d["payload"] = json.loads(d["payload"])
    if "acknowledged" in d:
        d["acknowledged"] = bool(d["acknowledged"])
    return d
