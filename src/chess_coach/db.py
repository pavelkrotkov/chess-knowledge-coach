from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'local',
    source_id TEXT,
    pgn TEXT NOT NULL,
    event TEXT, site TEXT, date TEXT, round TEXT,
    white TEXT NOT NULL, black TEXT NOT NULL, result TEXT NOT NULL,
    time_control TEXT, white_elo INTEGER, black_elo INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    fen TEXT NOT NULL,
    san TEXT NOT NULL,
    uci TEXT NOT NULL,
    clock_seconds REAL,
    UNIQUE(game_id, ply)
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    engine TEXT NOT NULL, engine_version TEXT NOT NULL,
    config_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS engine_outputs (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    score_cp INTEGER, wdl_json TEXT, best_move TEXT, played_move TEXT,
    pv TEXT, nodes INTEGER, depth INTEGER
);
CREATE TABLE IF NOT EXISTS detector_facts (
    id INTEGER PRIMARY KEY,
    position_id INTEGER REFERENCES positions(id) ON DELETE CASCADE,
    detector_version TEXT NOT NULL, fact_type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_mappings (
    id INTEGER PRIMARY KEY,
    position_id INTEGER REFERENCES positions(id) ON DELETE CASCADE,
    skill TEXT NOT NULL, operation TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN ('success', 'failure', 'ambiguous')),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    source_facts_json TEXT NOT NULL DEFAULT '[]',
    mapper_version TEXT NOT NULL DEFAULT '0.1.0',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_skill ON evidence_mappings(skill, operation);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
