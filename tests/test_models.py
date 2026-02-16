"""Tests for backend.models — Event, Alert, SystemMetrics, enums, helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.models.event import Event, EventSource, EventType
from backend.models.alert import Alert, Severity, SEVERITY_MULTIPLIER
from backend.models.metrics import SystemMetrics


# ── EventSource enum ──────────────────────────────────

class TestEventSource:
    def test_all_members_exist(self):
        expected = {
            "PORT_COLLECTOR", "PROCESS_COLLECTOR", "CONNECTION_COLLECTOR",
            "CPU_COLLECTOR", "FILE_COLLECTOR", "LOG_COLLECTOR", "SIMULATOR",
        }
        assert set(EventSource.__members__) == expected

    def test_values_are_snake_case(self):
        for member in EventSource:
            assert member.value == member.name.lower()


# ── EventType enum ────────────────────────────────────

class TestEventType:
    def test_all_members_exist(self):
        expected = {
            "PORT_OPEN", "PROCESS_RUNNING", "CONNECTION_ACTIVE",
            "CPU_USAGE", "FILE_CHANGED", "LOGIN_FAILED",
        }
        assert set(EventType.__members__) == expected

    def test_values_are_snake_case(self):
        for member in EventType:
            assert member.value == member.name.lower()


# ── Event model ───────────────────────────────────────

class TestEvent:
    def test_defaults(self):
        e = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE)
        assert len(e.id) == 12
        assert e.payload == {}
        assert isinstance(e.timestamp, datetime)
        assert e.timestamp.tzinfo is not None  # must be tz-aware

    def test_unique_ids(self):
        events = [
            Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE)
            for _ in range(50)
        ]
        ids = {e.id for e in events}
        assert len(ids) == 50

    def test_explicit_payload(self):
        e = Event(
            source=EventSource.PORT_COLLECTOR,
            event_type=EventType.PORT_OPEN,
            payload={"port": 4444, "pid": 1234},
        )
        assert e.payload["port"] == 4444
        assert e.payload["pid"] == 1234

    def test_serialization_round_trip(self):
        e = Event(
            source=EventSource.FILE_COLLECTOR,
            event_type=EventType.FILE_CHANGED,
            payload={"path": "/tmp/x"},
        )
        data = e.model_dump()
        e2 = Event.model_validate(data)
        assert e2.id == e.id
        assert e2.source == e.source
        assert e2.event_type == e.event_type
        assert e2.payload == e.payload


# ── Severity enum & multiplier ────────────────────────

class TestSeverity:
    def test_ordering(self):
        levels = list(Severity)
        assert levels == [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    def test_multiplier_values(self):
        assert SEVERITY_MULTIPLIER[Severity.LOW] == 1
        assert SEVERITY_MULTIPLIER[Severity.MEDIUM] == 2
        assert SEVERITY_MULTIPLIER[Severity.HIGH] == 3
        assert SEVERITY_MULTIPLIER[Severity.CRITICAL] == 4

    def test_all_severities_have_multiplier(self):
        for s in Severity:
            assert s in SEVERITY_MULTIPLIER


# ── Alert model ───────────────────────────────────────

class TestAlert:
    def test_defaults(self):
        a = Alert(rule_id="TEST_RULE", severity=Severity.HIGH)
        assert len(a.id) == 12
        assert a.base_score == 0.0
        assert a.message == ""
        assert a.source == ""
        assert a.payload == {}
        assert a.acknowledged is False
        assert a.created_at.tzinfo is not None

    def test_full_construction(self):
        a = Alert(
            rule_id="PORT_SUSPICIOUS",
            severity=Severity.CRITICAL,
            base_score=36.0,
            message="Unexpected port 4444",
            source="port_collector",
            payload={"port": 4444},
            acknowledged=True,
        )
        assert a.rule_id == "PORT_SUSPICIOUS"
        assert a.severity == Severity.CRITICAL
        assert a.base_score == 36.0
        assert a.acknowledged is True

    def test_serialization_round_trip(self):
        a = Alert(rule_id="R1", severity=Severity.LOW, payload={"k": "v"})
        data = a.model_dump()
        a2 = Alert.model_validate(data)
        assert a2.id == a.id
        assert a2.severity == a.severity


# ── SystemMetrics model ───────────────────────────────

class TestSystemMetrics:
    def test_defaults(self):
        m = SystemMetrics()
        assert m.cpu_percent == 0.0
        assert m.memory_percent == 0.0
        assert m.open_ports == 0
        assert m.active_connections == 0
        assert m.process_count == 0
        assert isinstance(m.timestamp, datetime)

    def test_custom_values(self):
        m = SystemMetrics(
            cpu_percent=87.3,
            memory_percent=55.1,
            open_ports=12,
            active_connections=42,
            process_count=300,
        )
        assert m.cpu_percent == 87.3
        assert m.open_ports == 12

    def test_serialization_round_trip(self):
        m = SystemMetrics(cpu_percent=50.0, process_count=100)
        data = m.model_dump()
        m2 = SystemMetrics.model_validate(data)
        assert m2.cpu_percent == m.cpu_percent
        assert m2.process_count == m.process_count
