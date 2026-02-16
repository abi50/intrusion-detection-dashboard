from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router, ws_manager
from backend.collectors import (
    ConnectionCollector,
    CpuCollector,
    FileCollector,
    LogCollector,
    PortCollector,
    ProcessCollector,
)
from backend.config import settings
from backend.db import database as db
from backend.engine import AlertManager, EventBus, RiskScorer, RulesEngine
from backend.models import Alert

logger = logging.getLogger(__name__)

# Resolve frontend build directory (works for both dev and Docker)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


async def _ws_broadcast(alert: Alert, risk_score: float) -> None:
    """AlertManager callback — push new alerts to all WebSocket clients."""
    await ws_manager.broadcast(
        {
            "type": "alert",
            "alert": alert.model_dump(mode="json"),
            "risk_score": risk_score,
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────
    await db.init_db()

    event_bus = EventBus()
    rules_engine = RulesEngine(settings.rules_file, settings.ip_blocklist_file)
    risk_scorer = RiskScorer(
        decay_lambda=settings.decay_lambda,
        max_score=settings.max_risk_score,
    )
    alert_manager = AlertManager(
        rules_engine=rules_engine,
        risk_scorer=risk_scorer,
        on_alert_callback=_ws_broadcast,
    )

    event_bus.subscribe(alert_manager.handle_event)
    await event_bus.start()

    collectors = [
        CpuCollector(event_bus, interval=settings.collect_interval),
        PortCollector(event_bus, interval=settings.collect_interval),
        ProcessCollector(event_bus, interval=settings.collect_interval),
        ConnectionCollector(event_bus, interval=settings.collect_interval),
        FileCollector(event_bus, monitored_dir=settings.monitored_directory, interval=settings.collect_interval),
        LogCollector(event_bus, interval=settings.collect_interval),
    ]
    for c in collectors:
        await c.start()

    # Store on app.state for route access
    app.state.event_bus = event_bus
    app.state.rules_engine = rules_engine
    app.state.risk_scorer = risk_scorer
    app.state.alert_manager = alert_manager
    app.state.collectors = collectors

    logger.info("IDS backend started — %d collectors active", len(collectors))

    yield

    # ── shutdown ──────────────────────────────────────
    for c in collectors:
        await c.stop()
    await event_bus.stop()
    logger.info("IDS backend shut down")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve the React frontend from /frontend/dist when it exists.
# In production (Docker or PyInstaller), the built SPA is served here.
# API routes are registered first, so /api/* and /ws/* still work.
if _FRONTEND_DIST.is_dir():
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="static-assets")

    # SPA catch-all: any non-API route returns index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
