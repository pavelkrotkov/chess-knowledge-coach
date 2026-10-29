"""Durable deep jobs, attempt history, and separately owned alternatives."""

import sqlite3


def add_deep_execution(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_analysis_jobs (
        id INTEGER PRIMARY KEY,
        selection_id INTEGER NOT NULL,
        position_id INTEGER NOT NULL,
        config_fingerprint TEXT NOT NULL,
        config_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','running','complete','insufficient','unstable','stale')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(selection_id, position_id, config_fingerprint),
        UNIQUE(id, selection_id, position_id),
        FOREIGN KEY(selection_id, position_id)
            REFERENCES deep_selection_items(selection_id, position_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_analysis_attempts (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES deep_analysis_jobs(id),
        attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
        status TEXT NOT NULL CHECK(status IN ('running','complete','insufficient','unstable','interrupted','stale')),
        detail TEXT NOT NULL,
        comparison TEXT NOT NULL CHECK(comparison IN ('comparable','incomparable','unknown')),
        analysis_run_id INTEGER REFERENCES analysis_runs(id),
        best_work_json TEXT,
        played_work_json TEXT,
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        finished_at TEXT,
        UNIQUE(job_id, attempt_number)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_analysis_alternatives (
        attempt_id INTEGER NOT NULL REFERENCES deep_analysis_attempts(id),
        rank INTEGER NOT NULL CHECK(rank > 0),
        line_json TEXT NOT NULL,
        PRIMARY KEY(attempt_id, rank)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_analysis_current (
        selection_id INTEGER NOT NULL,
        position_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        PRIMARY KEY(selection_id, position_id),
        FOREIGN KEY(job_id, selection_id, position_id)
            REFERENCES deep_analysis_jobs(id, selection_id, position_id)
    )""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_deep_jobs_selection ON deep_analysis_jobs(selection_id, status, id)"
    )
