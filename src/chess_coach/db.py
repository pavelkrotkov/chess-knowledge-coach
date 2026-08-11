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
    variant TEXT NOT NULL DEFAULT 'Standard', termination TEXT,
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
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY,
    skill TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    ontology_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skill_edges (
    parent_skill TEXT NOT NULL REFERENCES skills(skill) ON DELETE CASCADE,
    child_skill TEXT NOT NULL REFERENCES skills(skill) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    ontology_version TEXT NOT NULL,
    PRIMARY KEY(parent_skill, child_skill, edge_type, ontology_version)
);
CREATE TABLE IF NOT EXISTS opening_datasets (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL,
    source_url TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version, source_url)
);
CREATE TABLE IF NOT EXISTS opening_nodes (
    id INTEGER PRIMARY KEY,
    dataset_id INTEGER NOT NULL REFERENCES opening_datasets(id) ON DELETE CASCADE,
    position_key TEXT NOT NULL,
    eco TEXT,
    name TEXT NOT NULL,
    ply INTEGER NOT NULL,
    UNIQUE(dataset_id, position_key, name)
);
CREATE TABLE IF NOT EXISTS opening_edges (
    dataset_id INTEGER NOT NULL REFERENCES opening_datasets(id) ON DELETE CASCADE,
    parent_key TEXT NOT NULL,
    child_key TEXT NOT NULL,
    uci TEXT NOT NULL,
    PRIMARY KEY(dataset_id, parent_key, child_key)
);
CREATE TABLE IF NOT EXISTS game_openings (
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    dataset_id INTEGER NOT NULL REFERENCES opening_datasets(id) ON DELETE CASCADE,
    opening_node_id INTEGER REFERENCES opening_nodes(id),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    PRIMARY KEY(game_id, dataset_id)
);
CREATE INDEX IF NOT EXISTS idx_opening_nodes_position
    ON opening_nodes(dataset_id, position_key);
CREATE TABLE IF NOT EXISTS structure_episodes (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    start_ply INTEGER NOT NULL,
    end_ply INTEGER NOT NULL,
    features_json TEXT NOT NULL,
    structure_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    detector_version TEXT NOT NULL,
    UNIQUE(game_id, start_ply, end_ply, detector_version)
);
CREATE INDEX IF NOT EXISTS idx_structure_episodes_game
    ON structure_episodes(game_id, start_ply);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(games)")}
        if "variant" not in columns:
            self.connection.execute(
                "ALTER TABLE games ADD COLUMN variant TEXT NOT NULL DEFAULT 'Standard'"
            )
        if "termination" not in columns:
            self.connection.execute("ALTER TABLE games ADD COLUMN termination TEXT")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
