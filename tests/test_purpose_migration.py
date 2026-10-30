"""Synthetic purpose diagnostic coverage."""

import pytest

from chess_coach.deep_selection import select_deep
from tests.purpose_db_snapshot import (
    assert_legacy_data,
    assert_upgraded,
    disable_purpose_migration,
    schema_objects,
    set_schema28,
    typed_rows,
)
from tests.test_deep_selection import LEARNER, setup_game


def test_schema_28_upgrade_rolls_back_and_preserves_typed_history(tmp_path, monkeypatch):
    from chess_coach import db_recent

    original = disable_purpose_migration(monkeypatch, db_recent)
    db = setup_game(tmp_path / "schema28.sqlite", monkeypatch)
    select_deep(db, [1], learner=LEARNER, per_game=2, total=2)
    set_schema28(db)
    objects = schema_objects(db)
    tables = [row[1] for row in objects if row[0] == "table"]
    before = typed_rows(db, tables)
    assert_legacy_data(before)

    def fail_after_schema(connection):
        original(connection)
        raise RuntimeError("synthetic migration failure")

    monkeypatch.setattr(db_recent, "add_purpose_analysis", fail_after_schema)
    with pytest.raises(RuntimeError, match="synthetic migration failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 28
    assert objects == schema_objects(db)
    monkeypatch.setattr(db_recent, "add_purpose_analysis", original)
    db.initialize()
    assert_upgraded(db, tables, before, objects)


def test_foreign_purpose_schema_rejects_upgrade_without_mutation(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.db import Database

    original = disable_purpose_migration(monkeypatch, db_recent)
    db = Database(":memory:")
    db.initialize()
    db.connection.execute("PRAGMA user_version=28")
    db.connection.execute("CREATE TABLE purpose_analysis_requests(id INTEGER PRIMARY KEY)")
    db.connection.commit()
    before = list(db.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name"))
    monkeypatch.setattr(db_recent, "add_purpose_analysis", original)
    with pytest.raises(RuntimeError, match="foreign or incomplete purpose-analysis schema"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 28
    assert (
        list(db.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name"))
        == before
    )
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
