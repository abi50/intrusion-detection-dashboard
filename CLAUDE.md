# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local Intrusion Detection Dashboard — an interview project that simulates and detects suspicious system behavior in a defensive, legal way. It is NOT a real antivirus. It monitors local system metrics (ports, processes, CPU, files, auth logs, network connections), applies YAML-configurable detection rules, computes a time-decaying risk score, and pushes alerts to a React dashboard via WebSocket.

## Architecture

**Backend** (Python 3.11+ / FastAPI):
- `backend/collectors/` — async tasks using `psutil`, `watchdog`, and OS log parsers. All inherit from `BaseCollector` ABC with a `collect() -> list[Event]` method.
- `backend/engine/` — event bus (`asyncio.Queue`), YAML rules engine, risk scorer (weighted + exponential decay), alert manager (dedup + persist).
- `backend/api/` — REST routes (`/api/alerts`, `/api/metrics`, `/api/risk`, `/api/rules`, `/api/status`) and WebSocket (`/ws/events`).
- `backend/db/` — SQLite via `aiosqlite`. Schema in `db/schema.sql`.
- `backend/rules/` — `rules.yaml` (detection rules) and `ip_blocklist.csv`.

**Frontend** (React 18 / Vite / TypeScript):
- Tremor UI for dashboard components, Recharts for charts.
- `frontend/src/hooks/` — `useWebSocket`, `useAlerts`, `useMetrics` for data fetching.
- `frontend/src/pages/` — Dashboard (main view), Alerts (history), Settings (rules viewer).

**Simulator** (`simulator/`):
- Standalone Python scripts that generate realistic attack events (port scan, brute force, file tamper, CPU spike, suspicious connections) for demo purposes.

## Key Data Flow

Collectors (async tasks) → Event Bus (asyncio.Queue) → Rules Engine (YAML match) → Risk Scorer (weight × severity × e^(-0.005×age)) → Alert Manager → SQLite + WebSocket push → React Dashboard

## Risk Scoring Formula

```
base_score = rule.weight × severity_multiplier  (LOW=1, MED=2, HIGH=3, CRIT=4)
decayed_score = base_score × e^(-0.005 × age_seconds)
total_risk = min(Σ(decayed_scores), 100)
```

## Commands

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install
npm run dev          # dev server (Vite)
npm run build        # production build

# Simulator (run while backend is active)
cd simulator && python simulate.py

# Full stack (when Docker is set up)
docker-compose up
```

## Constraints

- Defensive only — no offensive capabilities, no payload generation, no exploitation code.
- All detection is rule-based via `rules.yaml` — no hardcoded thresholds in collector code.
- Collectors must be cross-platform (Windows + Linux) using `psutil` abstractions where possible. Platform-specific log parsing is isolated in `log_collector.py`.
- WebSocket is the primary real-time channel; REST is for historical queries and initial page loads.
- SQLite is the only required external dependency — no Redis, no Postgres.
