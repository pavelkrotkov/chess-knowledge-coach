"""Versioned selection snapshots; deep execution is a separate concern."""

import sqlite3


def add_deep_selection(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_selection_runs (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id),
        learner_key TEXT NOT NULL,
        cheap_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
        selector_version TEXT NOT NULL,
        input_fingerprint TEXT NOT NULL,
        selection_fingerprint TEXT NOT NULL,
        config_json TEXT NOT NULL,
        coverage_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(game_id, learner_key, selection_fingerprint),
        UNIQUE(id, game_id, learner_key)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_selection_items (
        selection_id INTEGER NOT NULL REFERENCES deep_selection_runs(id),
        position_id INTEGER NOT NULL REFERENCES positions(id),
        rank INTEGER NOT NULL CHECK(rank > 0),
        allocation TEXT NOT NULL CHECK(allocation IN ('control','score','uncertain','opportunity')),
        reasons_json TEXT NOT NULL,
        PRIMARY KEY(selection_id, position_id),
        UNIQUE(selection_id, rank)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS deep_selection_current (
        game_id INTEGER NOT NULL,
        learner_key TEXT NOT NULL,
        selection_id INTEGER NOT NULL,
        PRIMARY KEY(game_id, learner_key),
        FOREIGN KEY(selection_id, game_id, learner_key)
            REFERENCES deep_selection_runs(id, game_id, learner_key)
    )""")
