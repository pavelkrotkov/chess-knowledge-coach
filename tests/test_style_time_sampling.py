"""Chronological scope, ownership and projection invalidation."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.style_report import style_report
from chess_coach.style_time_candidates import recent_games


def game(day, *, white="Learner", black="Opponent", extra=""):
    return f"""[Event "Synthetic {day} {extra}"]
[White "{white}"]
[Black "{black}"]
[UTCDate "2026.01.{day}"]
[UTCTime "12:00:00"]
[Result "*"]

1. e4 e5 *
"""


def test_out_of_order_both_colors_and_boundary_tie():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, game("02"))
    ingest_pgn(db, game("01"))
    ingest_pgn(db, game("03", white="Opponent", black="Learner"))
    ingest_pgn(db, game("03", extra="second"))
    rows, coverage = recent_games(db, "Learner", limit=1)
    assert [(row["id"], color) for row, color in rows] == [(4, "white")]
    assert coverage["boundary_tie"] and coverage["game_limit_reached"]
    rows, _ = recent_games(db, "Learner", limit=3)
    assert [(row["id"], color) for row, color in rows] == [(4, "white"), (3, "black"), (1, "white")]
    report = style_report(db, "Learner", max_games=3)
    assert report["coverage"]["examined_games"] == 3
    assert report["selection_counts"]["games_without_selection"] == 3
    assert "game-start" in report["coverage"]["selection_order"]


def test_unknown_mutation_direct_insert_and_foreign_version():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, game("01"))
    ingest_pgn(db, game("02").replace("[UTCTime", "[OtherTime"))
    ingest_pgn(db, game("03").replace("2026.01.03", "2026.01.99"))
    ingest_pgn(db, game("04", white="Learner", black="Learner"))
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
        (game("05"), "Learner", "Opponent", "*"),
    )
    rows, info = recent_games(db, "Learner", limit=10)
    assert len(rows) == 1
    assert info["unknown_time_lower_bound"] == 2
    assert info["unknown_ownership_global_lower_bound"] == 2
    db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows and info["unknown_ownership_global_lower_bound"] == 3
    coverage = style_report(db, "Learner")["coverage"]
    assert coverage["unprocessed_decisions_unknown"]
    assert coverage["omitted_attributable_games_lower_bound"] == 2
    assert coverage["omitted_attributable_games_unknown"]


def test_duplicate_time_and_ownership_tags_are_not_ranked():
    db = Database(":memory:")
    db.initialize()
    ambiguous = game("01").replace(
        "[UTCTime", "[UTCDate " + chr(34) + "2026.01.02" + chr(34) + "]\n[UTCTime"
    )
    ingest_pgn(db, ambiguous, raw_pgn_override=ambiguous)
    white_tag = "[White " + chr(34) + "Learner" + chr(34) + "]"
    duplicate_owner = game("02").replace(white_tag, white_tag + "\n" + white_tag)
    ingest_pgn(db, duplicate_owner, raw_pgn_override=duplicate_owner)
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows
    assert info["unknown_time_lower_bound"] == 1
    assert info["unknown_ownership_global_lower_bound"] == 1


def test_rollback_on_projection_failure(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    original = db_recent.add_style_game_times
    monkeypatch.setattr(db_recent, "add_style_game_times", lambda connection: None)
    db.initialize()
    db.connection.execute("PRAGMA user_version=27")
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
        (game("01"), "Learner", "Opponent", "*"),
    )
    db.connection.commit()
    monkeypatch.setattr(db_recent, "add_style_game_times", original)
    from chess_coach import style_time_schema

    def fail(connection, game_id):
        raise RuntimeError("synthetic backfill failure")

    monkeypatch.setattr(style_time_schema, "update_projection", fail)
    with pytest.raises(RuntimeError, match="synthetic backfill failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 27
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name=?", ("style_game_times",)
        ).fetchone()[0]
        == 0
    )
    monkeypatch.undo()
    db.initialize()
    rows, _ = recent_games(db, "Learner", limit=10)
    assert len(rows) == 1


def test_indexed_lookup_limits_candidate_validation(monkeypatch):
    from chess_coach import style_time_candidates
    from chess_coach.style_time_projection import update_projection

    db = Database(":memory:")
    db.initialize()
    for number in range(120):
        cursor = db.connection.execute(
            "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
            (game("01", extra=str(number)), "Learner", "Opponent", "*"),
        )
        update_projection(db.connection, cursor.lastrowid)
    for side in ("white", "black"):
        plan = db.connection.execute(
            f"EXPLAIN QUERY PLAN SELECT game_id FROM style_game_times WHERE status=? AND version=? "
            f"AND {side}_identity=? ORDER BY started_at DESC,game_id DESC LIMIT ?",
            ("current", "utc-game-start-v1", "learner", 11),
        ).fetchall()
        assert any(f"idx_style_time_{side}" in row[3] for row in plan)
        assert all("TEMP B-TREE" not in row[3] for row in plan)
    validate = style_time_candidates.verified
    checked = []

    def counted(row, subject):
        checked.append(row["id"])
        return validate(row, subject)

    monkeypatch.setattr(style_time_candidates, "verified", counted)
    rows, info = recent_games(db, "Learner", limit=10)
    assert len(rows) == len(checked) == 10
    assert info["boundary_tie"] and info["game_limit_reached"]


def test_changed_or_foreign_projection_does_not_become_current():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, game("01"))
    db.connection.execute("UPDATE style_game_times SET version=? WHERE game_id=1", ("foreign",))
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows and info["unknown_ownership_global_lower_bound"] == 1
    db.connection.execute(
        "UPDATE style_game_times SET version=?,black_identity=? WHERE game_id=1",
        ("utc-game-start-v1", "tampered"),
    )
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows and info["candidate_recheck_failed"] == 1


def test_old_read_snapshot_and_next_request_see_source_change(tmp_path):
    from chess_coach.recurrence_snapshot import read_snapshot

    path = tmp_path / "snapshot.sqlite"
    first = Database(path)
    first.initialize()
    first.connection.execute("PRAGMA journal_mode=WAL")
    ingest_pgn(first, game("01"))
    second = Database(path)
    with read_snapshot(first):
        before, _ = recent_games(first, "Learner", limit=10)
        second.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
        second.connection.commit()
        during, _ = recent_games(first, "Learner", limit=10)
        assert len(before) == len(during) == 1
    after, info = recent_games(first, "Learner", limit=10)
    assert not after and info["unknown_ownership_global_lower_bound"] == 1
    first.close()
    second.close()


def test_migration_preserves_all_legacy_tables_and_source_rows(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    original = db_recent.add_style_game_times
    monkeypatch.setattr(db_recent, "add_style_game_times", lambda connection: None)
    db.initialize()
    db.connection.execute("PRAGMA user_version=27")
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
        (game("01"), "Learner", "Opponent", "*"),
    )
    db.connection.execute(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES(?,?,?,?,?)",
        (1, 1, "synthetic", "e4", "e2e4"),
    )
    db.connection.commit()
    tables = [
        row[0]
        for row in db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type=? AND name NOT LIKE ?", ("table", "sqlite_%")
        )
    ]
    before = {table: list(db.connection.execute(f"SELECT * FROM {table}")) for table in tables}
    monkeypatch.setattr(db_recent, "add_style_game_times", original)
    db.initialize()
    after = {table: list(db.connection.execute(f"SELECT * FROM {table}")) for table in tables}
    assert before == after
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 29


def test_foreign_projection_schema_fails_closed():
    db = Database(":memory:")
    db.initialize()
    db.connection.execute("DROP TRIGGER style_time_invalidate")
    db.connection.execute("PRAGMA user_version=27")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="foreign or incomplete style time projection"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 27


def test_nontext_legacy_pgn_remains_unknown():
    from chess_coach.style_time_projection import update_projection

    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES(?,?,?,?)",
        (b"\xff", "Learner", "Opponent", "*"),
    )
    update_projection(db.connection, 1)
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows and info["unknown_ownership_global_lower_bound"] == 1
    db.connection.execute(
        "UPDATE style_game_times SET version=?,status=?,started_at=?,white_identity=?,black_identity=?",
        ("utc-game-start-v1", "current", "2026-01-01T00:00:00+00:00", "learner", "opponent"),
    )
    rows, info = recent_games(db, "Learner", limit=10)
    assert not rows and info["candidate_recheck_failed"] == 1
