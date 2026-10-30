"""Explicit public promotion goals use durable bounded legal proof."""

from pathlib import Path

import chess
import pytest

from chess_coach.db import Database
from chess_coach.objective_promotion_contract import FORCE, NOW
from chess_coach.objective_promotion_judge import judge
from chess_coach.objective_worker import process
from chess_coach.public_training import import_collection
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "src/chess_coach/data/promotion_objectives/canonical.csv"
MANIFEST = ROOT / "src/chess_coach/data/promotion_objectives/manifest.json"
VERSION = "canonical-promotion-v1"
SUBJECT = "fixture_learner"


def setup_db(path):
    db = Database(path)
    db.initialize()
    result = import_collection(db, CONTENT, CONTENT, MANIFEST, project_root=ROOT)
    assert result == {"version": VERSION, "accepted": 8, "excluded": 0}
    return db


def begin(db, key, attempt):
    return start(
        db, attempt_id=attempt, subject=SUBJECT, source_type="public", version=VERSION, key=key
    )


def oriented(text, black):
    move = chess.Move.from_uci(text)
    if black:
        move = chess.Move(
            chess.square_mirror(move.from_square),
            chess.square_mirror(move.to_square),
            promotion=move.promotion,
        )
    return move.uci()


@pytest.mark.parametrize("black", [False, True])
def test_immediate_promotion_including_stalemate_and_capture(black):
    board = chess.Board("7k/P4K2/8/5B2/8/8/8/8 w - - 0 1")
    if black:
        board = board.mirror()
    move = board.parse_uci(oriented("a7a8n", black))
    result = judge(board, move, NOW, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "correct" and result["reason"] == "promotion_performed"
    board.push(move)
    assert board.is_stalemate()
    capture = chess.Board("r6k/1PK5/8/8/8/8/8/8 w - - 0 1")
    if black:
        capture = capture.mirror()
    move = capture.parse_uci(oriented("b7a8n", black))
    assert (
        capture.is_capture(move)
        and judge(capture, move, NOW, lambda: 0.0, 0.0, 5.0, {})["status"] == "correct"
    )


def test_imported_source_queues_exemplar_and_resumes_every_defense(tmp_path):
    db = setup_db(tmp_path / "promotion.sqlite")
    before = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
    state = begin(db, "forced-white", "forced")
    assert state["objective"] == FORCE
    original = submit(db, "forced", SUBJECT, event_id="root", move="a6a7")
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("root",)
    ).fetchone()[0]
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    resumed = show(db, "forced", SUBJECT)
    assert resumed["status"] == "active" and resumed["promotion_continuation"]
    board = chess.Board(resumed["fen"])
    move = next(move for move in board.legal_moves if move.promotion == chess.KNIGHT)
    final = submit(db, "forced", SUBJECT, event_id="final", move=move.uci())
    assert final["status"] == "objective_verified"
    assert submit(db, "forced", SUBJECT, event_id="root", move="a6a7") == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("root",)
        ).fetchone()[0]
        == frozen
    )
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == before
