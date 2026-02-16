from __future__ import annotations

import csv
import ipaddress
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from backend.models import Alert, Event, Severity, SEVERITY_MULTIPLIER

logger = logging.getLogger(__name__)


class RuleCondition(BaseModel):
    field: str
    operator: str
    value: Any
    sustained_seconds: int | None = None
    window_seconds: int | None = None


class RuleDefinition(BaseModel):
    id: str
    description: str = ""
    source: str
    severity: Severity
    weight: float
    condition: RuleCondition


class RulesEngine:
    """Evaluates events against YAML-defined detection rules."""

    def __init__(
        self,
        rules_path: str | Path,
        blocklist_path: str | Path | None = None,
    ) -> None:
        self._rules_path = Path(rules_path)
        self._blocklist_path = Path(blocklist_path) if blocklist_path else None
        self.rules: list[RuleDefinition] = self.load_rules()
        self.blocklist: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = (
            self.load_blocklist() if self._blocklist_path else []
        )

    def load_rules(self) -> list[RuleDefinition]:
        raw = yaml.safe_load(self._rules_path.read_text())
        entries = raw.get("rules", []) if isinstance(raw, dict) else raw
        rules: list[RuleDefinition] = []
        for entry in entries:
            try:
                rules.append(RuleDefinition(**entry))
            except Exception:
                logger.warning("Skipping invalid rule: %s", entry.get("id", "?"))
        return rules

    def load_blocklist(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        if not self._blocklist_path or not self._blocklist_path.exists():
            return []
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        with open(self._blocklist_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ip_str = row.get("ip", "").strip()
                if not ip_str:
                    continue
                try:
                    networks.append(ipaddress.ip_network(ip_str, strict=False))
                except ValueError:
                    logger.warning("Skipping invalid CIDR: %s", ip_str)
        return networks

    def evaluate(self, event: Event) -> list[Alert]:
        """Evaluate an event against all matching rules. Returns generated alerts."""
        alerts: list[Alert] = []
        for rule in self.rules:
            if rule.source != event.source.value:
                continue
            if self._check_condition(rule.condition, event.payload):
                sev_mult = SEVERITY_MULTIPLIER[rule.severity]
                base_score = rule.weight * sev_mult
                alert = Alert(
                    rule_id=rule.id,
                    severity=rule.severity,
                    base_score=base_score,
                    message=rule.description,
                    source=event.source.value,
                    payload=dict(event.payload),
                )
                alerts.append(alert)
        return alerts

    def _check_condition(self, cond: RuleCondition, payload: dict) -> bool:
        field_val = payload.get(cond.field)
        if field_val is None:
            return False

        op = cond.operator
        rule_val = cond.value

        if op == "gt":
            return float(field_val) > float(rule_val)
        elif op == "lt":
            return float(field_val) < float(rule_val)
        elif op == "gte":
            return float(field_val) >= float(rule_val)
        elif op == "lte":
            return float(field_val) <= float(rule_val)
        elif op == "eq":
            return self._eq(field_val, rule_val)
        elif op == "neq":
            return not self._eq(field_val, rule_val)
        elif op == "in":
            return field_val in rule_val
        elif op == "not_in":
            return field_val not in rule_val
        elif op == "in_blocklist":
            return self._check_blocklist(str(field_val))
        else:
            logger.warning("Unknown operator: %s", op)
            return False

    @staticmethod
    def _eq(field_val: Any, rule_val: Any) -> bool:
        """Equality supporting bool/str/int coercion."""
        if isinstance(rule_val, bool) or (
            isinstance(rule_val, str) and rule_val.lower() in ("true", "false")
        ):
            fv = field_val if isinstance(field_val, bool) else str(field_val).lower() == "true"
            rv = rule_val if isinstance(rule_val, bool) else str(rule_val).lower() == "true"
            return fv == rv
        return str(field_val) == str(rule_val)

    def _check_blocklist(self, ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(addr in net for net in self.blocklist)
