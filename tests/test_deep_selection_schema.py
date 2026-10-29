"""Selection schema upgrades preserve history and constrain ownership."""

import sqlite3

import pytest

from chess_coach.db import Database


def test_selection_schema_migrates_v16_atomically_and_preserves_history(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "selection.sqlite")
    db.initialize()
    db.connection.execute("DROP TABLE deep_selection_current")
    db.connection.execute("DROP TABLE deep_selection_items")
    db.connection.execute("DROP TABLE deep_selection_runs")
    db.connection.execute("PRAGMA user_version=16")
    db.connection.execute("INSERT INTO games(pgn,white,black,result) VALUES('fixture','A','B','*')")
    db.connection.commit()
    original = db_recent.add_deep_selection

    def fail(connection):
        original(connection)
        raise ValueError("synthetic upgrade failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_deep_selection", fail)
        with pytest.raises(ValueError, match="synthetic upgrade failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 16
    assert (
        db.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='deep_selection_runs'"
        ).fetchone()
        is None
    )
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 18
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_current_pointer_cannot_reference_another_game_or_learner(tmp_path):
    db = Database(tmp_path / "ownership.sqlite")
    db.initialize()
    db.connection.execute("INSERT INTO games(pgn,white,black,result) VALUES('fixture','A','B','*')")
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,'test','v1','{}')"
    )
    db.connection.execute("""INSERT INTO deep_selection_runs
        (game_id,learner_key,cheap_run_id,selector_version,input_fingerprint,selection_fingerprint,config_json,coverage_json)
        VALUES(1,'hash-a',1,'v1','input','selection','{}','{}')""")
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("INSERT INTO deep_selection_current VALUES(1,'hash-b',1)")
