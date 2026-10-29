"""Store comparable engine lines without rewriting legacy analysis."""

import sqlite3


def add_comparison_lines(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS decision_analysis_lines (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
        position_id INTEGER NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK(role IN ('best', 'played')),
        semantics TEXT NOT NULL,
        decision_fen TEXT NOT NULL,
        score_pov TEXT NOT NULL,
        root_move TEXT,
        score_kind TEXT CHECK(score_kind IN ('cp', 'mate')),
        score_value INTEGER,
        score_bound TEXT CHECK(score_bound IN ('exact', 'lower', 'upper')),
        wdl_json TEXT,
        pv TEXT,
        nodes INTEGER,
        depth INTEGER,
        seldepth INTEGER,
        time_seconds REAL,
        UNIQUE(run_id, position_id, role)
    )""")
