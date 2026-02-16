"""Attack event simulator for the Intrusion Detection Dashboard.

Generates realistic events (port scan, brute force, file tamper,
CPU spike, suspicious connections) and publishes them to the backend
via its REST API or directly into the EventBus when imported.

Usage:
    python simulator/simulate.py              # run all scenarios
    python simulator/simulate.py --scenario port_scan
    python simulator/simulate.py --api http://localhost:8000  # push via WS
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.engine.event_bus import EventBus
from backend.models.event import Event, EventSource, EventType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SIM] %(message)s")
logger = logging.getLogger("simulator")


# ── Scenario generators ──────────────────────────────


async def port_scan(bus: EventBus, count: int = 8, delay: float = 0.5) -> None:
    """Simulate suspicious ports appearing."""
    suspicious_ports = [4444, 5555, 6666, 7777, 8888, 9999, 1337, 31337]
    for port in random.sample(suspicious_ports, min(count, len(suspicious_ports))):
        event = Event(
            source=EventSource.PORT_COLLECTOR,
            event_type=EventType.PORT_OPEN,
            payload={"port": port, "pid": random.randint(1000, 9999), "process": "suspicious_svc"},
        )
        await bus.publish(event)
        logger.info("Port scan: port %d opened", port)
        await asyncio.sleep(delay)


async def brute_force(bus: EventBus, attempts: int = 12, delay: float = 0.3) -> None:
    """Simulate failed login attempts."""
    users = ["root", "admin", "user", "test", "deploy", "postgres"]
    for i in range(attempts):
        event = Event(
            source=EventSource.LOG_COLLECTOR,
            event_type=EventType.LOGIN_FAILED,
            payload={
                "failed_logins": i + 1,
                "window_seconds": 60,
                "username": random.choice(users),
            },
        )
        await bus.publish(event)
        logger.info("Brute force: attempt %d/%d", i + 1, attempts)
        await asyncio.sleep(delay)


async def file_tamper(bus: EventBus, count: int = 3, delay: float = 1.0) -> None:
    """Simulate monitored file hash changes."""
    files = ["/etc/passwd", "/etc/shadow", "/etc/ssh/sshd_config", "C:\\Windows\\System32\\config\\SAM"]
    for path in random.sample(files, min(count, len(files))):
        event = Event(
            source=EventSource.FILE_COLLECTOR,
            event_type=EventType.FILE_CHANGED,
            payload={
                "path": path,
                "hash_match": False,
                "old_hash": f"{random.getrandbits(64):016x}",
                "new_hash": f"{random.getrandbits(64):016x}",
            },
        )
        await bus.publish(event)
        logger.info("File tampered: %s", path)
        await asyncio.sleep(delay)


async def cpu_spike(bus: EventBus, duration: int = 6, delay: float = 1.0) -> None:
    """Simulate sustained high CPU usage."""
    for i in range(duration):
        pct = round(random.uniform(92, 99), 1)
        event = Event(
            source=EventSource.CPU_COLLECTOR,
            event_type=EventType.CPU_USAGE,
            payload={"percent": pct, "sustained": i >= 3, "duration_seconds": i * 5},
        )
        await bus.publish(event)
        logger.info("CPU spike: %.1f%% (tick %d/%d)", pct, i + 1, duration)
        await asyncio.sleep(delay)


async def suspicious_connections(bus: EventBus, count: int = 5, delay: float = 0.8) -> None:
    """Simulate outbound connections to blocklisted IPs."""
    blocklist_ips = [
        "10.66.66.10", "10.66.66.20", "10.66.66.30",
        "198.51.100.5", "203.0.113.42", "192.0.2.99",
    ]
    for ip in random.sample(blocklist_ips, min(count, len(blocklist_ips))):
        event = Event(
            source=EventSource.CONNECTION_COLLECTOR,
            event_type=EventType.CONNECTION_ACTIVE,
            payload={
                "remote_ip": ip,
                "remote_port": random.choice([443, 8080, 4444, 1337]),
                "local_port": random.randint(49152, 65535),
                "pid": random.randint(1000, 9999),
                "process": random.choice(["unknown", "suspicious.exe", "backdoor"]),
            },
        )
        await bus.publish(event)
        logger.info("Suspicious connection: -> %s", ip)
        await asyncio.sleep(delay)


async def suspicious_process(bus: EventBus, delay: float = 1.0) -> None:
    """Simulate suspicious process names appearing."""
    procs = [
        ("nc", 6001), ("mimikatz", 6002), ("reverse_shell", 6003),
        ("cryptominer", 6004), ("ncat", 6005),
    ]
    for name, pid in procs:
        event = Event(
            source=EventSource.PROCESS_COLLECTOR,
            event_type=EventType.PROCESS_RUNNING,
            payload={"name": name, "pid": pid, "username": "attacker"},
        )
        await bus.publish(event)
        logger.info("Suspicious process: %s (PID %d)", name, pid)
        await asyncio.sleep(delay)


SCENARIOS = {
    "port_scan": port_scan,
    "brute_force": brute_force,
    "file_tamper": file_tamper,
    "cpu_spike": cpu_spike,
    "suspicious_connections": suspicious_connections,
    "suspicious_process": suspicious_process,
}


# ── Main runner ──────────────────────────────────────


async def run_all(bus: EventBus) -> None:
    """Run all scenarios sequentially with pauses between them."""
    for name, fn in SCENARIOS.items():
        logger.info("=== Starting scenario: %s ===", name)
        await fn(bus)
        await asyncio.sleep(2)
    logger.info("=== All scenarios complete ===")


async def main() -> None:
    parser = argparse.ArgumentParser(description="IDS Attack Simulator")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), help="Run a single scenario")
    args = parser.parse_args()

    # Import and wire into the running backend
    from backend.config import settings
    from backend.db import database as db
    from backend.engine import AlertManager, RiskScorer, RulesEngine

    await db.init_db()

    bus = EventBus()
    rules_engine = RulesEngine(settings.rules_file, settings.ip_blocklist_file)
    risk_scorer = RiskScorer(decay_lambda=settings.decay_lambda, max_score=settings.max_risk_score)
    alert_manager = AlertManager(rules_engine=rules_engine, risk_scorer=risk_scorer)

    bus.subscribe(alert_manager.handle_event)
    await bus.start()

    if args.scenario:
        logger.info("Running scenario: %s", args.scenario)
        await SCENARIOS[args.scenario](bus)
    else:
        await run_all(bus)

    # Let the bus drain
    await asyncio.sleep(2)
    await bus.stop()
    logger.info("Simulator finished. Alerts persisted to DB.")


if __name__ == "__main__":
    asyncio.run(main())
