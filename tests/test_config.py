"""Tests for backend.config — Settings defaults and env override."""

from __future__ import annotations

from pathlib import Path


class TestSettings:
    def test_default_values(self):
        from backend.config import Settings
        s = Settings()
        assert s.app_name == "Intrusion Detection Dashboard"
        assert s.debug is False
        assert s.collect_interval == 5.0
        assert s.decay_lambda == 0.005
        assert s.max_risk_score == 100.0
        assert s.host == "0.0.0.0"
        assert s.port == 8000
        assert "http://localhost:5173" in s.cors_origins

    def test_db_path_points_to_db_dir(self):
        from backend.config import Settings
        s = Settings()
        assert s.db_path.endswith("ids.db")
        assert "db" in s.db_path

    def test_rules_file_points_to_yaml(self):
        from backend.config import Settings
        s = Settings()
        assert s.rules_file.endswith("rules.yaml")

    def test_ip_blocklist_path(self):
        from backend.config import Settings
        s = Settings()
        assert s.ip_blocklist_file.endswith("ip_blocklist.csv")

    def test_base_dir_and_rules_dir(self):
        from backend.config import BASE_DIR, RULES_DIR
        assert BASE_DIR.is_dir()
        assert RULES_DIR == BASE_DIR / "rules"

    def test_env_prefix(self):
        from backend.config import Settings
        assert Settings.model_config["env_prefix"] == "IDS_"
