"""Deep job schema upgrades preserve history and enforce selection ownership."""

import sqlite3

import pytest

from chess_coach.db import Database


def test_v18_upgrade_is_atomic_and_idempotent(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "upgrade.sqlite")
    db.initialize()
    db.connection.execute("DROP TABLE deep_analysis_alternatives")
    db.connection.execute("DROP TABLE deep_analysis_attempts")
    db.connection.execute("DROP TABLE deep_analysis_jobs")
    db.connection.execute("PRAGMA user_version=18")
    db.connection.execute("INSERT INTO games(pgn,white,black,result) VALUES('fixture','A','B','*')")
    db.connection.commit()
    original = db_recent.add_deep_execution

    def fail(connection):
        original(connection)
        raise ValueError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_deep_execution", fail)
        with pytest.raises(ValueError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 18
    assert (
        db.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='deep_analysis_jobs'"
        ).fetchone()
        is None
    )
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 19
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_job_requires_a_selected_position(tmp_path):
    db = Database(tmp_path / "foreign.sqlite")
    db.initialize()
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("""INSERT INTO deep_analysis_jobs
        (selection_id,position_id,config_fingerprint,config_json,status) VALUES(1,1,'x','{}','pending')""")
