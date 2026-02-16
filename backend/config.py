from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
RULES_DIR = BASE_DIR / "rules"


class Settings(BaseSettings):
    # --- app ---
    app_name: str = "Intrusion Detection Dashboard"
    debug: bool = False

    # --- database ---
    db_path: str = str(BASE_DIR / "db" / "ids.db")

    # --- rules ---
    rules_file: str = str(RULES_DIR / "rules.yaml")
    ip_blocklist_file: str = str(RULES_DIR / "ip_blocklist.csv")

    # --- collectors ---
    collect_interval: float = 5.0  # seconds between collection cycles
    monitored_directory: str = str(BASE_DIR.parent / "monitored_files")

    # --- risk scoring ---
    decay_lambda: float = 0.005  # exponential decay constant
    max_risk_score: float = 100.0

    # --- server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_prefix": "IDS_"}


settings = Settings()
