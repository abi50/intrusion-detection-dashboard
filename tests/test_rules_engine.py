"""Tests for backend.engine.rules_engine."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.engine.rules_engine import RulesEngine
from backend.models import Event, EventSource, EventType, Severity


# ── helpers ────────────────────────────────────────────

def _write_yaml(tmp_path: Path, yaml_text: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(textwrap.dedent(yaml_text))
    return p


def _write_blocklist(tmp_path: Path, cidrs: list[str]) -> Path:
    p = tmp_path / "blocklist.csv"
    lines = ["ip,label"] + [f"{c},test" for c in cidrs]
    p.write_text("\n".join(lines))
    return p


BASIC_RULES = """\
rules:
  - id: HIGH_CPU
    description: "CPU above 90"
    source: cpu_collector
    condition:
      field: percent
      operator: gt
      value: 90
    severity: MEDIUM
    weight: 4

  - id: PORT_NOT_ALLOWED
    description: "Unexpected port"
    source: port_collector
    condition:
      field: port
      operator: not_in
      value: [22, 80, 443]
    severity: HIGH
    weight: 8

  - id: PROC_BAD
    description: "Bad process"
    source: process_collector
    condition:
      field: name
      operator: in
      value: [mimikatz, nc]
    severity: CRITICAL
    weight: 9

  - id: FILE_TAMPER
    description: "Hash mismatch"
    source: file_collector
    condition:
      field: hash_match
      operator: eq
      value: false
    severity: CRITICAL
    weight: 9

  - id: CONN_BLOCK
    description: "Blocklisted IP"
    source: connection_collector
    condition:
      field: remote_ip
      operator: in_blocklist
      value: "blocklist.csv"
    severity: HIGH
    weight: 8
"""


# ── tests ──────────────────────────────────────────────

class TestOperatorGt:
    def test_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 95})
        alerts = engine.evaluate(event)
        assert len(alerts) == 1
        assert alerts[0].rule_id == "HIGH_CPU"

    def test_no_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 50})
        assert engine.evaluate(event) == []


class TestOperatorLt:
    def test_lt(self, tmp_path: Path):
        yaml_text = """\
        rules:
          - id: LOW_CPU
            description: "Low CPU"
            source: cpu_collector
            condition: {field: percent, operator: lt, value: 10}
            severity: LOW
            weight: 1
        """
        engine = RulesEngine(_write_yaml(tmp_path, yaml_text))
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 5})
        assert len(engine.evaluate(event)) == 1


class TestOperatorGteLte:
    def test_gte(self, tmp_path: Path):
        yaml_text = """\
        rules:
          - id: GTE_TEST
            description: "GTE"
            source: cpu_collector
            condition: {field: percent, operator: gte, value: 90}
            severity: LOW
            weight: 1
        """
        engine = RulesEngine(_write_yaml(tmp_path, yaml_text))
        event_eq = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 90})
        event_below = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 89})
        assert len(engine.evaluate(event_eq)) == 1
        assert engine.evaluate(event_below) == []

    def test_lte(self, tmp_path: Path):
        yaml_text = """\
        rules:
          - id: LTE_TEST
            description: "LTE"
            source: cpu_collector
            condition: {field: percent, operator: lte, value: 10}
            severity: LOW
            weight: 1
        """
        engine = RulesEngine(_write_yaml(tmp_path, yaml_text))
        event_eq = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 10})
        event_above = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 11})
        assert len(engine.evaluate(event_eq)) == 1
        assert engine.evaluate(event_above) == []


class TestOperatorEqNeq:
    def test_eq_bool_false(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.FILE_COLLECTOR, event_type=EventType.FILE_CHANGED, payload={"hash_match": False})
        alerts = engine.evaluate(event)
        assert len(alerts) == 1
        assert alerts[0].rule_id == "FILE_TAMPER"

    def test_eq_bool_true_no_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.FILE_COLLECTOR, event_type=EventType.FILE_CHANGED, payload={"hash_match": True})
        assert engine.evaluate(event) == []

    def test_neq(self, tmp_path: Path):
        yaml_text = """\
        rules:
          - id: NEQ_TEST
            description: "Not equal"
            source: cpu_collector
            condition: {field: status, operator: neq, value: "ok"}
            severity: LOW
            weight: 1
        """
        engine = RulesEngine(_write_yaml(tmp_path, yaml_text))
        event_fail = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"status": "error"})
        event_ok = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"status": "ok"})
        assert len(engine.evaluate(event_fail)) == 1
        assert engine.evaluate(event_ok) == []


class TestOperatorInNotIn:
    def test_in(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.PROCESS_COLLECTOR, event_type=EventType.PROCESS_RUNNING, payload={"name": "nc"})
        alerts = engine.evaluate(event)
        assert len(alerts) == 1
        assert alerts[0].rule_id == "PROC_BAD"

    def test_in_no_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.PROCESS_COLLECTOR, event_type=EventType.PROCESS_RUNNING, payload={"name": "python"})
        assert engine.evaluate(event) == []

    def test_not_in_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.PORT_COLLECTOR, event_type=EventType.PORT_OPEN, payload={"port": 9999})
        alerts = engine.evaluate(event)
        assert len(alerts) == 1
        assert alerts[0].rule_id == "PORT_NOT_ALLOWED"

    def test_not_in_no_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.PORT_COLLECTOR, event_type=EventType.PORT_OPEN, payload={"port": 80})
        assert engine.evaluate(event) == []


class TestBlocklist:
    def test_in_blocklist(self, tmp_path: Path):
        _write_blocklist(tmp_path, ["10.66.66.0/24", "192.0.2.0/24"])
        engine = RulesEngine(
            _write_yaml(tmp_path, BASIC_RULES),
            blocklist_path=tmp_path / "blocklist.csv",
        )
        event = Event(
            source=EventSource.CONNECTION_COLLECTOR,
            event_type=EventType.CONNECTION_ACTIVE,
            payload={"remote_ip": "10.66.66.5"},
        )
        alerts = engine.evaluate(event)
        assert len(alerts) == 1
        assert alerts[0].rule_id == "CONN_BLOCK"

    def test_not_in_blocklist(self, tmp_path: Path):
        _write_blocklist(tmp_path, ["10.66.66.0/24"])
        engine = RulesEngine(
            _write_yaml(tmp_path, BASIC_RULES),
            blocklist_path=tmp_path / "blocklist.csv",
        )
        event = Event(
            source=EventSource.CONNECTION_COLLECTOR,
            event_type=EventType.CONNECTION_ACTIVE,
            payload={"remote_ip": "8.8.8.8"},
        )
        assert engine.evaluate(event) == []


class TestSourceFiltering:
    def test_rule_only_matches_its_source(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"port": 9999})
        alerts = engine.evaluate(event)
        # PORT_NOT_ALLOWED should NOT match a cpu_collector event
        assert all(a.rule_id != "PORT_NOT_ALLOWED" for a in alerts)


class TestBaseScore:
    def test_correct_base_score(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        # PROC_BAD: weight=9, severity=CRITICAL (mult=4) → 36
        event = Event(source=EventSource.PROCESS_COLLECTOR, event_type=EventType.PROCESS_RUNNING, payload={"name": "mimikatz"})
        alerts = engine.evaluate(event)
        assert alerts[0].base_score == 9 * 4

    def test_medium_base_score(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        # HIGH_CPU: weight=4, severity=MEDIUM (mult=2) → 8
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={"percent": 99})
        alerts = engine.evaluate(event)
        assert alerts[0].base_score == 4 * 2


class TestMissingField:
    def test_missing_payload_field_no_match(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.CPU_COLLECTOR, event_type=EventType.CPU_USAGE, payload={})
        assert engine.evaluate(event) == []


class TestNoMatchReturnsEmpty:
    def test_no_rules_for_source(self, tmp_path: Path):
        engine = RulesEngine(_write_yaml(tmp_path, BASIC_RULES))
        event = Event(source=EventSource.SIMULATOR, event_type=EventType.CPU_USAGE, payload={"percent": 99})
        assert engine.evaluate(event) == []
