from __future__ import annotations

import json
import subprocess
import sys

import chess

from chess_coach.db import Database


def test_puzzle_cli_resumes_and_verifies_across_processes(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    csv = tmp_path / "puzzles.csv"
    csv.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation\n"
        f"p1,{chess.STARTING_FEN},e2e4 e7e5 g1f3 b8c6,1200,80\n"
    )

    def run(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "chess_coach.cli", "--db", str(path), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    assert run("import-puzzles", str(csv), "--version", "v1") == {"rows": 1}
    start = run("start-puzzle", "v1", "p1", "attempt")
    board = chess.Board()
    board.push_uci("e2e4")
    assert start["fen"] == board.fen()
    assert "e7e5" not in json.dumps(start)
    assert run("show-puzzle", "attempt") == start
    hint = run("hint-puzzle", "attempt", "--event-id", "hint")
    assert hint["hint"] == "e7" and hint["hints_used"] == 1
    assert run("hint-puzzle", "attempt", "--event-id", "hint") == hint
    illegal = run("play-puzzle", "attempt", "0000", "--event-id", "bad")
    assert illegal["feedback"] == "illegal" and illegal["fen"] == start["fen"]
    first = run("play-puzzle", "attempt", "e7e5", "--event-id", "first")
    assert first["opponent_move"] == "g1f3" and first["status"] == "active"
    assert "b8c6" not in json.dumps(first)
    assert run("play-puzzle", "attempt", "e7e5", "--event-id", "first") == first
    assert run("show-puzzle", "attempt")["fen"] == first["fen"]
    last = run("play-puzzle", "attempt", "b8c6", "--event-id", "last")
    assert last["status"] == "solved" and last["hints_used"] == 1
    assert run("play-puzzle", "attempt", "b8c6", "--event-id", "last") == last
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 4
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_malformed_puzzle_cli_error_does_not_reveal_solution(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    csv = tmp_path / "puzzles.csv"
    csv.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation\n"
        f"p1,{chess.STARTING_FEN},e2e4 e7e5 g1f3 z9z9,1200,80\n"
    )
    base = [sys.executable, "-m", "chess_coach.cli", "--db", str(path)]
    subprocess.run(
        [*base, "import-puzzles", str(csv), "--version", "v1"], check=True, capture_output=True
    )
    result = subprocess.run(
        [*base, "start-puzzle", "v1", "p1", "attempt"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "invalid puzzle position or solution" in result.stderr
    assert "z9z9" not in result.stderr


def test_puzzle_cli_can_complete_verified_training_feedback(tmp_path) -> None:
    path = tmp_path / "coach.sqlite"
    csv = tmp_path / "puzzles.csv"
    csv.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation\n"
        "p1,6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1,g8h8 c5f8,1200,80\n"
    )

    def run(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "chess_coach.cli", "--db", str(path), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    run("import-puzzles", str(csv), "--version", "v1")
    run("start-puzzle", "v1", "p1", "attempt")
    item = run("create-puzzle-training", "v1", "p1", "mate_in_one", "execute")["id"]
    prompt = run("show-puzzle", "attempt", "--training-item-id", str(item))
    assert prompt["training_objective"] == "Find mate in one."
    assert "c5f8" not in json.dumps(prompt) and "c5c8" not in json.dumps(prompt)
    args = (
        "play-puzzle",
        "attempt",
        "c5c8",
        "--event-id",
        "move",
        "--training-item-id",
        str(item),
        "--subject",
        "learner",
    )
    result = run(*args)
    assert result["status"] == "solved" and result["training"]["evidence_id"] is not None
    assert run(*args) == result
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 1
    assert db.connection.execute("SELECT human_validated FROM evidence_mappings").fetchone()[0] == 0
