"""Capture typed legacy data and schema for migration regressions."""


def schema_objects(db):
    rows = db.connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE ?", ("sqlite_%",)
    )
    return {tuple(row) for row in rows}


def typed_rows(db, tables):
    return {
        name: [
            tuple((type(value), value) for value in row)
            for row in db.connection.execute(f'SELECT * FROM "{name}"')
        ]
        for name in tables
    }


def assert_legacy_data(before):
    assert before["games"]
    assert before["positions"]
    assert before["analysis_runs"]
    assert before["deep_selection_current"]


def assert_upgraded(db, tables, before, objects):
    assert typed_rows(db, tables) == before
    assert objects <= schema_objects(db)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 31
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def disable_purpose_migration(monkeypatch, db_recent):
    original = db_recent.add_purpose_analysis
    monkeypatch.setattr(db_recent, "add_purpose_analysis", lambda _connection: None)
    return original


def set_schema28(db):
    db.connection.execute("PRAGMA user_version=28")
    db.connection.commit()
