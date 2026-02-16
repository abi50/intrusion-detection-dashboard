from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from backend.db import database as db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── WebSocket connection manager ──────────────────────


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


# ── REST routes ───────────────────────────────────────


@router.get("/api/alerts")
async def get_alerts(
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    return await db.get_alerts(severity=severity, limit=limit, offset=offset)


@router.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: str) -> dict:
    row = await db.get_alert_by_id(alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row


@router.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str) -> dict:
    ok = await db.acknowledge_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"acknowledged": True}


@router.get("/api/metrics")
async def get_metrics(minutes: int = 30) -> list[dict]:
    return await db.get_metrics_history(minutes=minutes)


@router.get("/api/risk")
async def get_risk(limit: int = 360) -> list[dict]:
    return await db.get_risk_history(limit=limit)


@router.get("/api/rules")
async def get_rules(request: Request) -> list[dict]:
    rules_engine = request.app.state.rules_engine
    return [r.model_dump() for r in rules_engine.rules]


@router.get("/api/status")
async def get_status(request: Request) -> dict:
    state = request.app.state
    event_bus = state.event_bus
    collectors = getattr(state, "collectors", [])
    return {
        "status": "running",
        "event_bus_running": event_bus.running,
        "subscribers": event_bus.subscriber_count,
        "pending_events": event_bus.pending,
        "collectors": len(collectors),
    }


# ── WebSocket endpoint ────────────────────────────────


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings or messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
