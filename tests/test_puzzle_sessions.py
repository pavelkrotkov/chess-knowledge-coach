from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import chess
import pytest

from chess_coach.db import SCHEMA, Database
from chess_coach.puzzle_sessions import request_hint, show_attempt, start_attempt, submit_move
from chess_coach.puzzles import import_puzzles


def corpus(
    db: Database, *, fen: str = chess.STARTING_FEN, solution: str = "e2e4 e7e5 g1f3 b8c6"
) -> None:
    db.connection.execute(
        "INSERT INTO puzzle_corpora (version, source, checksum) VALUES ('v1', 'fixture', 'hash-v1')"
    )
    db.connection.execute(
        """INSERT INTO puzzles
        (puzzle_id, corpus_id, fen, source, solution, rating, rating_deviation, themes_json, objective)
        VALUES ('p1', 1, ?, '', ?, 1200, 80, '[]', 'calculate')""",
        (fen, solution),
    )
    db.connection.commit()


def database(path=":memory:", **puzzle) -> Database:
    db = Database(path)
    db.initialize()
    corpus(db, **puzzle)
    return db


def test_setup_alternation_resume_hints_and_retry(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    db = database(path)
    first = start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    board = chess.Board()
    board.push_uci("e2e4")
    assert first["fen"] == board.fen()
    assert first["status"] == "active"
    assert "e7e5" not in json.dumps(first)
    assert start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1") == first
    with pytest.raises(ValueError, match="another puzzle"):
        start_attempt(db, attempt_id="a1", version="v1", puzzle_id="other")

    hint = request_hint(db, "a1", event_id="hint-1")
    assert hint["hint"] == "e7" and hint["hints_used"] == 1
    assert request_hint(db, "a1", event_id="hint-1") == hint
    result = submit_move(db, "a1", event_id="move-1", move="e7e5")
    board.push_uci("e7e5")
    board.push_uci("g1f3")
    assert result["fen"] == board.fen()
    assert result["opponent_move"] == "g1f3"
    assert result["feedback"] == "correct" and result["status"] == "active"
    assert "b8c6" not in json.dumps(result)
    db.close()

    db = Database(path)
    assert show_attempt(db, "a1")["fen"] == board.fen()
    assert submit_move(db, "a1", event_id="move-1", move="e7e5") == result
    complete = submit_move(db, "a1", event_id="move-2", move="b8c6")
    assert complete["status"] == "solved" and complete["finished_at"]
    assert submit_move(db, "a1", event_id="move-2", move="b8c6") == complete
    with pytest.raises(ValueError, match="already complete"):
        submit_move(db, "a1", event_id="move-3", move="a7a6")
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 3
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_illegal_and_wrong_moves_are_distinct_and_retries_are_idempotent() -> None:
    db = database()
    initial = start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    for event, move in (("illegal", "e7e4"), ("null", "0000"), ("bad", "not-uci")):
        result = submit_move(db, "a1", event_id=event, move=move)
        assert result["feedback"] == "illegal" and result["fen"] == initial["fen"]
        assert submit_move(db, "a1", event_id=event, move=move) == result
    with pytest.raises(ValueError, match="different request"):
        submit_move(db, "a1", event_id="illegal", move="d7d5")
    wrong = submit_move(db, "a1", event_id="wrong", move="d7d5")
    assert wrong["feedback"] == "incorrect" and wrong["status"] == "failed"
    assert wrong["finished_at"] and wrong["opponent_move"] is None
    assert submit_move(db, "a1", event_id="wrong", move="d7d5") == wrong
    with pytest.raises(ValueError, match="already complete"):
        request_hint(db, "a1", event_id="after")


@pytest.mark.parametrize(
    ("fen", "solution"),
    [
        ("not-fen", "e2e4 e7e5"),
        (chess.STARTING_FEN, ""),
        (chess.STARTING_FEN, "e2e4"),
        (chess.STARTING_FEN, "0000 e2e4"),
        (chess.STARTING_FEN, "e2e4 e7e4"),
        (chess.STARTING_FEN, "e2e4 e7e5 g1f3 b8c9"),
    ],
)
def test_invalid_corpus_rejected_before_session_is_created(fen, solution) -> None:
    db = database(fen=fen, solution=solution)
    with pytest.raises(ValueError, match="invalid puzzle"):
        start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_sessions").fetchone()[0] == 0


def test_promotion_and_alternative_mate() -> None:
    db = database(fen="7k/P7/8/8/8/8/8/7K b - - 0 1", solution="h8g7 a7a8q")
    start_attempt(db, attempt_id="promotion", version="v1", puzzle_id="p1")
    assert submit_move(db, "promotion", event_id="m1", move="a7a8q")["status"] == "solved"
    mate = database(fen="6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1", solution="g8h8 c5f8")
    start_attempt(mate, attempt_id="mate", version="v1", puzzle_id="p1")
    result = submit_move(mate, "mate", event_id="m1", move="c5c8")
    assert result["status"] == "solved"
    assert isinstance(result["fen"], str)
    assert chess.Board(result["fen"]).is_checkmate()


def test_reimport_does_not_delete_attempt_or_change_its_snapshot(tmp_path) -> None:
    path = tmp_path / "puzzles.csv"
    path.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation\n"
        f"p1,{chess.STARTING_FEN},e2e4 e7e5 g1f3 b8c6,1200,80\n"
    )
    db = Database(":memory:")
    db.initialize()
    import_puzzles(db, path, version="v1")
    start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    checksum = db.connection.execute("SELECT checksum FROM puzzle_corpora").fetchone()[0]
    import_puzzles(db, path, version="v1")
    snapshot = db.connection.execute(
        "SELECT corpus_checksum, initial_fen, solution FROM puzzle_sessions"
    ).fetchone()
    assert tuple(snapshot) == (checksum, chess.STARTING_FEN, "e2e4 e7e5 g1f3 b8c6")
    assert submit_move(db, "a1", event_id="m1", move="e7e5")["status"] == "active"


def test_concurrent_identical_event_is_applied_once(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    db = database(path)
    start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    db.close()

    def submit():
        connection = Database(path)
        try:
            return submit_move(connection, "a1", event_id="m1", move="e7e5")
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: submit(), range(2)))
    assert first == second
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 1
    assert show_attempt(db, "a1")["fen"] == first["fen"]


def test_schema_v4_upgrade_preserves_cursor_and_creates_session_tables(monkeypatch) -> None:
    from chess_coach import db_recent

    db = Database(":memory:")
    db.connection.executescript(SCHEMA)
    db.connection.execute("PRAGMA user_version = 4")
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('existing', 'A', 'B', '*')"
    )
    db.connection.execute(
        """INSERT INTO sync_progress
        (account_key, revision, next_kind, history_start, history_windows, history_cycles,
         recent_windows, recent_end, recent_target)
        VALUES ('synthetic', 7, 'history', 20, '[[20,30]]', 2, '[[25,30]]', 25, 30)"""
    )
    db.connection.commit()

    def fail_after_first_table(connection):
        connection.execute("CREATE TABLE puzzle_sessions (attempt_id TEXT PRIMARY KEY)")
        raise RuntimeError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_puzzle_sessions", fail_after_first_table)
        with pytest.raises(RuntimeError, match="injected migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 4
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'puzzle_sessions'"
        ).fetchone()[0]
        == 0
    )

    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 17
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == "existing"
    row = db.connection.execute("SELECT * FROM sync_progress").fetchone()
    assert (row["revision"], row["next_kind"], row["history_windows"]) == (
        7,
        "history",
        "[[20,30]]",
    )
    assert (row["recent_windows"], row["recent_end"], row["recent_target"]) == ("[[25,30]]", 25, 30)
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_sessions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_puzzle_resolution_uses_corpus_version() -> None:
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora (version, source, checksum) VALUES ('v2', 'fixture', 'hash-v2')"
    )
    db.connection.execute(
        """INSERT INTO puzzles
        (puzzle_id, corpus_id, fen, source, solution, rating, rating_deviation, themes_json, objective)
        VALUES ('p1', 2, ?, '', 'd2d4 d7d5', 1200, 80, '[]', 'calculate')""",
        (chess.STARTING_FEN,),
    )
    db.connection.commit()
    first = start_attempt(db, attempt_id="first", version="v1", puzzle_id="p1")
    second = start_attempt(db, attempt_id="second", version="v2", puzzle_id="p1")
    assert first["fen"] != second["fen"]
    assert submit_move(db, "second", event_id="m1", move="d7d5")["status"] == "solved"
    with pytest.raises(ValueError, match="unknown versioned puzzle"):
        start_attempt(db, attempt_id="missing", version="v3", puzzle_id="p1")


def test_failed_event_write_rolls_back_state_and_can_be_retried() -> None:
    import sqlite3

    db = database()
    initial = start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    db.connection.execute(
        """CREATE TRIGGER reject_event BEFORE INSERT ON puzzle_session_events
        BEGIN SELECT RAISE(ABORT, 'injected failure'); END"""
    )
    db.connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        submit_move(db, "a1", event_id="m1", move="e7e5")
    assert show_attempt(db, "a1") == initial
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0
    db.connection.execute("DROP TRIGGER reject_event")
    db.connection.commit()
    assert submit_move(db, "a1", event_id="m1", move="e7e5")["status"] == "active"


def test_opponent_mating_line_is_rejected_before_start() -> None:
    board = chess.Board()
    board.push_uci("f2f3")
    db = database(fen=board.fen(), solution="e7e5 g2g4 d8h4")
    with pytest.raises(ValueError, match="invalid puzzle"):
        start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_sessions").fetchone()[0] == 0


@pytest.mark.parametrize("solution", ["e7e5 g2g4 d8h4", "e7e5 g2g4 d8h4 e2e4"])
def test_corrupt_snapshot_opponent_mate_cannot_complete_as_solved(solution) -> None:
    board = chess.Board()
    board.push_uci("f2f3")
    db = database(fen=board.fen(), solution="e7e5 g2g4")
    initial = start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    # Simulate a damaged database despite the snapshot immutability guard.
    db.connection.execute("DROP TRIGGER puzzle_session_snapshot_no_update")
    db.connection.execute(
        "UPDATE puzzle_sessions SET solution = ? WHERE attempt_id = ?",
        (solution, "a1"),
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="invalid puzzle"):
        submit_move(db, "a1", event_id="m1", move="g2g4")
    assert show_attempt(db, "a1") == initial
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0
