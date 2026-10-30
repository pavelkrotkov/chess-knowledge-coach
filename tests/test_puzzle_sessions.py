from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import chess
import pytest

from chess_coach.db import Database
from chess_coach.puzzle_sessions import request_hint, show_attempt, start_attempt, submit_move


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
