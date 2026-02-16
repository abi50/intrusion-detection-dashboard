CREATE TABLE IF NOT EXISTS alerts (
    id            TEXT PRIMARY KEY,
    rule_id       TEXT    NOT NULL,
    severity      TEXT    NOT NULL,
    base_score    REAL    NOT NULL DEFAULT 0.0,
    message       TEXT    NOT NULL DEFAULT '',
    source        TEXT    NOT NULL DEFAULT '',
    payload       TEXT    NOT NULL DEFAULT '{}',
    acknowledged  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity   ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_rule_id    ON alerts(rule_id);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    timestamp   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

CREATE TABLE IF NOT EXISTS metrics_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_percent         REAL    NOT NULL,
    memory_percent      REAL    NOT NULL,
    open_ports          INTEGER NOT NULL,
    active_connections  INTEGER NOT NULL,
    process_count       INTEGER NOT NULL,
    timestamp           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics_history(timestamp);

CREATE TABLE IF NOT EXISTS risk_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    score     REAL NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_history(timestamp);
