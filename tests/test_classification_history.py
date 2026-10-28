"""Classification lineage, legacy upgrades and atomic replay."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.openings import classify_game, import_openings
from chess_coach.structures import extract_game_episodes

PGN = """[Event "Fixture"]
[White "A"]
[Black "B"]
[Result "*"]

1. d4 d5 2. Nf3 Nf6 *
"""


@pytest.fixture
def db():
    result = Database(":memory:")
    result.initialize()
    ingest_pgn(result, PGN)
    return result


def test_structure_replay_versions_empty_run_and_current_view(db):
    assert extract_game_episodes(db, 1, detector_version="v1") > 0
    first = [
        tuple(row)
        for row in db.connection.execute(
            "SELECT id, run_id, produced_at FROM structure_episodes ORDER BY id"
        )
    ]
    assert first and all(row[1] and row[2] for row in first)
    assert extract_game_episodes(db, 1, detector_version="v1") == len(first)
    assert [
        tuple(row)
        for row in db.connection.execute(
            "SELECT id, run_id, produced_at FROM structure_episodes ORDER BY id"
        )
    ] == first
    assert extract_game_episodes(db, 1, detector_version="v2") == len(first)
    assert extract_game_episodes(db, 1, detector_version="v1") == len(first)
    assert db.connection.execute("SELECT COUNT(*) FROM structure_episodes").fetchone()[
        0
    ] == 2 * len(first)
    assert db.connection.execute("SELECT COUNT(*) FROM current_structure_episodes").fetchone()[
        0
    ] == len(first)
    assert (
        db.connection.execute(
            "SELECT detector_version FROM structure_runs WHERE status='active'"
        ).fetchone()[0]
        == "v2"
    )
    db.connection.execute("DELETE FROM positions WHERE game_id=1")
    db.connection.commit()
    assert extract_game_episodes(db, 1, detector_version="v2") == 0
    assert (
        db.connection.execute("SELECT COUNT(*) FROM current_structure_episodes").fetchone()[0] == 0
    )
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 3


def test_structure_same_version_changed_input_preserves_generation(db):
    extract_game_episodes(db, 1)
    first = db.connection.execute("SELECT id FROM structure_runs").fetchone()[0]
    db.connection.execute("DELETE FROM positions WHERE game_id=1 AND ply=2")
    db.connection.commit()
    extract_game_episodes(db, 1)
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 2
    assert (
        db.connection.execute("SELECT status FROM structure_runs WHERE id=?", (first,)).fetchone()[
            0
        ]
        == "superseded"
    )
    assert (
        db.connection.execute("SELECT COUNT(DISTINCT run_id) FROM structure_episodes").fetchone()[0]
        == 2
    )


def test_structure_failure_preserves_active_generation(db, monkeypatch):
    from chess_coach import structure_history

    extract_game_episodes(db, 1, detector_version="v1")
    original = structure_history._append_run

    def fail(*args):
        original(*args)
        raise RuntimeError("injected")

    monkeypatch.setattr(structure_history, "_append_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        extract_game_episodes(db, 1, detector_version="v2")
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT status FROM structure_runs").fetchone()[0] == "active"


def test_opening_no_match_dataset_changes_versions_and_replay(db, tmp_path):
    source = tmp_path / "openings.tsv"
    source.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, source, version="v1", source_url="fixture://openings")
    assert classify_game(db, 1, version="v1", source_url="fixture://openings")["matched"] is False
    first = tuple(
        db.connection.execute(
            "SELECT id, run_id, produced_at, opening_node_id FROM game_openings"
        ).fetchone()
    )
    assert first[1] and first[2] and first[3] is None
    classify_game(db, 1, version="v1", source_url="fixture://openings")
    assert (
        tuple(
            db.connection.execute(
                "SELECT id, run_id, produced_at, opening_node_id FROM game_openings"
            ).fetchone()
        )
        == first
    )
    source.write_text("eco\tname\tmoves\nD00\tClosed\td4 d5 Nf3 Nf6\n")
    import_openings(db, source, version="v1", source_url="fixture://openings")
    assert classify_game(db, 1, version="v1", source_url="fixture://openings")["name"] == "Closed"
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 2
    assert (
        db.connection.execute(
            "SELECT opening_node_id FROM game_openings WHERE id=?", (first[0],)
        ).fetchone()[0]
        is None
    )
    classify_game(db, 1, version="v1", source_url="fixture://openings", classifier_version="2")
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 3
    classify_game(db, 1, version="v1", source_url="fixture://openings")
    assert (
        db.connection.execute(
            "SELECT classifier_version FROM opening_runs WHERE status='active'"
        ).fetchone()[0]
        == "2"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM current_game_openings").fetchone()[0] == 1


def test_opening_failure_after_run_switch_rolls_back(db, tmp_path, monkeypatch):
    from chess_coach import opening_history

    source = tmp_path / "openings.tsv"
    source.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, source, version="v1", source_url="fixture://openings")
    classify_game(db, 1, version="v1", source_url="fixture://openings")
    original = opening_history._append_run

    def fail(*args):
        original(*args)
        raise RuntimeError("injected")

    monkeypatch.setattr(opening_history, "_append_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        classify_game(db, 1, version="v1", source_url="fixture://openings", classifier_version="2")
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT status FROM opening_runs").fetchone()[0] == "active"


def test_v7_upgrade_preserves_legacy_rows_and_custom_objects(monkeypatch):
    from chess_coach import db_recent

    legacy = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_classification_lineage", lambda connection: None)
        legacy.initialize()
    legacy.connection.execute("PRAGMA user_version=7")
    legacy.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES ('raw','A','B','*')"
    )
    legacy.connection.execute(
        "INSERT INTO opening_datasets(version,source_url) VALUES ('old','fixture://old')"
    )
    legacy.connection.execute("INSERT INTO game_openings VALUES (1,1,NULL,0.5)")
    legacy.connection.execute("""INSERT INTO structure_episodes
        (game_id,start_ply,end_ply,features_json,structure_json,confidence,detector_version)
        VALUES (1,1,2,'{}','[]',1,'old')""")
    legacy.connection.execute(
        "CREATE INDEX custom_structure ON structure_episodes(detector_version)"
    )
    legacy.connection.execute("CREATE TABLE trigger_log (episode INTEGER)")
    legacy.connection.execute("""CREATE TRIGGER custom_episode AFTER INSERT ON structure_episodes
        BEGIN INSERT INTO trigger_log VALUES (NEW.id); END""")
    legacy.connection.commit()
    legacy.initialize()
    row = legacy.connection.execute(
        "SELECT id, detector_version, run_id, produced_at FROM structure_episodes"
    ).fetchone()
    assert tuple(row) == (1, "old", None, None)
    opening = legacy.connection.execute(
        "SELECT game_id,dataset_id,confidence,run_id,produced_at FROM game_openings"
    ).fetchone()
    assert tuple(opening) == (1, 1, 0.5, None, None)
    assert (
        legacy.connection.execute("SELECT COUNT(*) FROM current_structure_episodes").fetchone()[0]
        == 0
    )
    assert (
        legacy.connection.execute("SELECT COUNT(*) FROM current_game_openings").fetchone()[0] == 0
    )
    legacy.connection.execute("""INSERT INTO structure_episodes
        (game_id,start_ply,end_ply,features_json,structure_json,confidence,detector_version)
        VALUES (1,3,4,'{}','[]',1,'old')""")
    assert legacy.connection.execute("SELECT COUNT(*) FROM trigger_log").fetchone()[0] == 1
    assert legacy.connection.execute(
        "SELECT name FROM sqlite_master WHERE name='custom_structure'"
    ).fetchone()
    assert legacy.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v8_failed_migration_rolls_back(monkeypatch):
    from chess_coach import db_recent

    legacy = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_classification_lineage", lambda connection: None)
        legacy.initialize()
    legacy.connection.execute("PRAGMA user_version=7")
    legacy.connection.commit()
    original = db_recent.add_classification_lineage
    before = [
        tuple(row)
        for row in legacy.connection.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY name"
        )
    ]

    def fail(connection):
        original(connection)
        raise RuntimeError("injected migration")

    monkeypatch.setattr(db_recent, "add_classification_lineage", fail)
    with pytest.raises(RuntimeError, match="injected migration"):
        legacy.initialize()
    assert legacy.connection.execute("PRAGMA user_version").fetchone()[0] == 7
    assert [
        tuple(row)
        for row in legacy.connection.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY name"
        )
    ] == before


def test_changed_output_same_input_and_versions_is_rejected(db, tmp_path, monkeypatch):
    from chess_coach import opening_classification, structure_episodes

    extract_game_episodes(db, 1, detector_version="v1")
    monkeypatch.setattr(structure_episodes, "_group_episodes", lambda rows: [])
    with pytest.raises(ValueError, match="structure output changed"):
        extract_game_episodes(db, 1, detector_version="v1")
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 1

    source = tmp_path / "openings.tsv"
    source.write_text("eco\tname\tmoves\nD00\tClosed\td4 d5 Nf3 Nf6\n")
    import_openings(db, source, version="v1", source_url="fixture://openings")
    classify_game(db, 1, version="v1", source_url="fixture://openings")
    monkeypatch.setattr(opening_classification, "_best_match", lambda *args: None)
    with pytest.raises(ValueError, match="opening output changed"):
        classify_game(db, 1, version="v1", source_url="fixture://openings")
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 1


def test_old_no_match_replay_does_not_reactivate(db, tmp_path):
    source = tmp_path / "openings.tsv"
    source.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, source, version="v1", source_url="fixture://one")
    classify_game(db, 1, version="v1", source_url="fixture://one")
    source.write_text("eco\tname\tmoves\nD00\tClosed\td4 d5 Nf3 Nf6\n")
    import_openings(db, source, version="v2", source_url="fixture://two")
    assert classify_game(db, 1, version="v2", source_url="fixture://two")["matched"] is True
    assert classify_game(db, 1, version="v1", source_url="fixture://one")["matched"] is False
    row = db.connection.execute("""SELECT d.version FROM current_game_openings o
        JOIN opening_datasets d ON d.id=o.dataset_id""").fetchone()
    assert row[0] == "v2"
    assert db.connection.execute("SELECT COUNT(*) FROM game_openings").fetchone()[0] == 2


def test_classification_does_not_commit_existing_transaction(db):
    db.connection.execute("UPDATE games SET event='pending' WHERE id=1")
    extract_game_episodes(db, 1)
    assert db.connection.in_transaction
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT event FROM games WHERE id=1").fetchone()[0] == "Fixture"
