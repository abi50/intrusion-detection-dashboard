from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
