# Intrusion Detection Dashboard

A real-time, local intrusion detection system that monitors your machine for suspicious activity and displays alerts on a live dashboard.

Built with **FastAPI**, **React**, **WebSocket**, and **psutil** — fully containerized with Docker.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-18-blue)
![Tests](https://img.shields.io/badge/Tests-155%20passing-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

The system continuously monitors six data sources on the host machine:

| Collector | Monitors | Example Alert |
|-----------|----------|---------------|
| **Port** | Open listening ports | Unexpected port 4444 opened |
| **Process** | Running processes | `mimikatz` or `cryptominer` detected |
| **CPU** | CPU & memory usage | Sustained usage above 90% |
| **Connection** | Active network connections | Outbound connection to blocklisted IP |
| **File** | File integrity (SHA-256) | `/etc/passwd` hash changed |
| **Log** | Auth/login logs | 10 failed logins in 60 seconds |

Events are evaluated against **YAML-configurable detection rules**, scored with an **exponential-decay risk formula**, deduplicated, and pushed to the dashboard in real time via WebSocket.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Dashboard                       │
│         (Risk gauge, charts, alerts table)               │
│                   Port 8000 (or 5173 dev)                │
└──────────────┬──────────────────────┬───────────────────┘
               │ REST API             │ WebSocket
               │ /api/*               │ /ws/events
┌──────────────┴──────────────────────┴───────────────────┐
│                   FastAPI Backend                        │
│                                                         │
│  ┌───────────┐   ┌───────────┐   ┌──────────────────┐  │
│  │ Collectors │──>│ Event Bus │──>│  Rules Engine     │  │
│  │ (psutil)  │   │ (asyncio) │   │  (YAML matching)  │  │
│  └───────────┘   └───────────┘   └────────┬─────────┘  │
│                                           │             │
│                       ┌───────────────────┴──────┐      │
│                       │   Alert Manager          │      │
│                       │  (dedup + risk scorer)   │      │
│                       └───────────┬──────────────┘      │
│                                   │                     │
│                          ┌────────┴────────┐            │
│                          │    SQLite DB    │            │
│                          └─────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

**Data flow:** Collectors → Event Bus → Rules Engine → Risk Scorer → Alert Manager → SQLite + WebSocket → Dashboard

---

## Risk Scoring

Alerts are scored using a weighted exponential decay formula:

```
base_score  = rule.weight × severity_multiplier
                (LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4)

decay       = e^(-0.005 × age_in_seconds)

total_risk  = min( Σ(base_score × decay), 100 )
```

Recent alerts contribute more to the risk score. Old alerts naturally fade away.

---

## Quick Start

### Option 1: Docker (recommended)

```bash
git clone https://github.com/abi50/intrusion-detection-dashboard.git
cd intrusion-detection-dashboard
docker-compose up --build
```

Open **http://localhost:5173** — the dashboard is live and monitoring your system.

**Run the attack simulator** to see the dashboard in action:

```bash
docker-compose --profile simulate up simulator
```

### Option 2: Run locally

**Prerequisites:** Python 3.11+, Node.js 18+

```bash
# Backend
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev

# Simulator (separate terminal, optional)
python -m simulator.simulate
```

Open **http://localhost:5173** (dev) or **http://localhost:8000** (single-process mode).

### Option 3: Single process (no frontend dev server)

Build the frontend once, then the backend serves everything on one port:

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** — both API and dashboard on one port.

---

## Dashboard Features

### Main Dashboard
- **Risk Score Gauge** — color-coded (green/yellow/red) real-time risk level
- **System Status** — collector count, event bus status, pending events
- **Risk Trend Chart** — line chart showing risk score over time
- **CPU & Memory Chart** — area chart of system resource usage
- **Recent Alerts** — last 10 alerts, live-updating via WebSocket

### Alerts Page
- Full alert history with severity filter (LOW / MEDIUM / HIGH / CRITICAL)
- One-click acknowledge button per alert
- Pagination for browsing historical alerts

### Settings Page
- View all loaded detection rules
- Rule details: source, severity, condition, weight

---

## Detection Rules

Rules are defined in `backend/rules/rules.yaml` and are fully customizable:

```yaml
rules:
  - id: PORT_SUSPICIOUS
    description: "Unexpected listening port detected"
    source: port_collector
    condition:
      field: port
      operator: not_in
      value: [22, 80, 443, 8000, 8080]
    severity: HIGH
    weight: 8

  - id: PROCESS_SUSPICIOUS
    description: "Known-suspicious process name detected"
    source: process_collector
    condition:
      field: name
      operator: in
      value: [nc, ncat, mimikatz, cryptominer]
    severity: CRITICAL
    weight: 9
```

**Supported operators:** `gt`, `lt`, `gte`, `lte`, `eq`, `neq`, `in`, `not_in`, `in_blocklist`

---

## Attack Simulator

The simulator generates realistic attack scenarios for demo and testing:

| Scenario | What it simulates |
|----------|-------------------|
| `port_scan` | Suspicious ports opening (4444, 1337, etc.) |
| `brute_force` | Rapid failed login attempts |
| `file_tamper` | Critical system file hash changes |
| `cpu_spike` | Sustained high CPU usage |
| `suspicious_connections` | Connections to blocklisted IPs |
| `suspicious_process` | Known-malicious process names |

```bash
# Run all scenarios
python -m simulator.simulate

# Run a specific scenario
python -m simulator.simulate --scenario port_scan
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | System status (event bus, collectors) |
| `GET` | `/api/alerts?severity=&limit=&offset=` | Alert history with filters |
| `GET` | `/api/alerts/{id}` | Single alert details |
| `POST` | `/api/alerts/{id}/acknowledge` | Acknowledge an alert |
| `GET` | `/api/metrics?minutes=` | CPU/memory metrics history |
| `GET` | `/api/risk?limit=` | Risk score history |
| `GET` | `/api/rules` | Loaded detection rules |
| `WS` | `/ws/events` | Real-time alert stream |

---

## Project Structure

```
├── backend/
│   ├── api/            # FastAPI routes + WebSocket
│   ├── collectors/     # 6 system monitors (psutil-based)
│   ├── db/             # SQLite database + schema
│   ├── engine/         # Event bus, rules engine, risk scorer, alert manager
│   ├── models/         # Pydantic models (Event, Alert, Metrics)
│   ├── rules/          # YAML rules + IP blocklist
│   ├── config.py       # App settings (env-configurable)
│   └── main.py         # FastAPI app entrypoint
├── frontend/
│   └── src/
│       ├── hooks/      # useWebSocket, useAlerts, useMetrics, useRisk, useStatus
│       ├── pages/      # Dashboard, Alerts, Settings
│       └── components/ # Layout, RiskGauge, AlertsTable
├── simulator/          # Attack scenario generator
├── tests/              # 155 tests (pytest)
├── Dockerfile          # Multi-stage build (frontend + backend)
├── Dockerfile.frontend # Nginx-based frontend container
├── docker-compose.yml  # Full stack orchestration
└── nginx.conf          # Reverse proxy config
```

---

## Tests

```bash
pytest tests/ -v
```

155 tests covering: rules engine (19), risk scorer (9), alert manager (7), API endpoints (9), and all 6 collectors (28), plus models, event bus, and database.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn, asyncio |
| Database | SQLite (aiosqlite) |
| System monitoring | psutil, watchdog |
| Rules | YAML-based with 9 operators |
| Frontend | React 18, TypeScript, Vite |
| UI Components | Tremor UI, Recharts |
| Real-time | WebSocket (native) |
| Containerization | Docker, docker-compose, nginx |

---

## Configuration

All settings are configurable via environment variables (prefix `IDS_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `IDS_COLLECT_INTERVAL` | `5.0` | Seconds between collection cycles |
| `IDS_DECAY_LAMBDA` | `0.005` | Risk score decay constant |
| `IDS_MAX_RISK_SCORE` | `100.0` | Risk score cap |
| `IDS_DEBUG` | `false` | Enable debug logging |

---

## License

MIT
