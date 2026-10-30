"""Synthetic mover-perspective WDL intervals and immutable pawn continuations."""

import json

import chess
import chess.syzygy

from chess_coach import pawn_proof, pawn_tables
from chess_coach.objective_pawn_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.pawn_coach_detector import process_decision
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_mate_proof import owned_game

FEN = "8/8/8/8/2k5/4K3/3P4/8 w - - 0 1"
SUBJECT = "fixture_a"


def synthetic_proof(board, *, goal=1):
    values = {"e3e4": (goal, goal), "e3f3": (goal, goal), "d2d4": (-1, -1), "e3f4": (0, 1)}
    return {
        "status": "complete",
        "lower": goal,
        "upper": goal,
        "nodes": 10,
        "alternatives": [
            {
                "move": {"uci": m.uci(), "san": board.san(m)},
                "lower": values.get(m.uci(), (-1, 1))[0],
                "upper": values.get(m.uci(), (-1, 1))[1],
            }
            for m in board.legal_moves
        ],
    }


def setup_game(path, monkeypatch):
    board = chess.Board(FEN)
    proof = synthetic_proof(board)
    db = owned_game(path, monkeypatch, fen=FEN, move="d4")
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    evidence = process_decision(db, 1, SUBJECT)["evidence_ids"][0]

    def evaluate(position, **kwargs):
        if position.turn == chess.WHITE and not position.move_stack:
            return proof
        if position.turn == chess.WHITE:
            return {
                "status": "complete",
                "lower": 1,
                "upper": 1,
                "nodes": 10,
                "alternatives": [
                    {"move": {"uci": move.uci()}, "lower": 1, "upper": 1}
                    for move in position.legal_moves
                ],
            }
        return {
            "status": "complete",
            "lower": -1,
            "upper": -1,
            "nodes": 10,
            "alternatives": [
                {"move": {"uci": move.uci()}, "lower": -1, "upper": -1}
                for move in position.legal_moves
            ],
        }

    monkeypatch.setattr(pawn_proof, "inspect_reused", evaluate)
    return db, evidence


def begin(db, evidence, attempt):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def data():
    return {
        "proof_version": pawn_proof.VERSION,
        "proof_manifest_sha256": pawn_tables.MANIFEST_SHA256,
    }


def test_owned_unlisted_result_and_legal_training_continuation(tmp_path, monkeypatch):
    db, evidence = setup_game(tmp_path / "pawn.sqlite", monkeypatch)
    tracked = ("evidence_mappings", "mastery_events", "training_items", "training_attempts")
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    }
    state = begin(db, evidence, "pawn")
    assert state["objective"] == "preserve_pawn_win"
    original = submit(db, "pawn", SUBJECT, event_id="answer", move="e3f3")
    assert original["feedback"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
    ).fetchone()[0]
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["continuation"]["status"] == "available"
    resumed = show(db, "pawn", SUBJECT)
    assert resumed["status"] == "active" and resumed["pawn_continuation"]
    board = chess.Board(resumed["fen"])
    next_move = next(iter(board.legal_moves)).uci()
    event = submit(db, "pawn", SUBJECT, event_id="continue", move=next_move)
    assert event["feedback"] == "needs_verification" and event["status"] == "needs_verification"
    pending = show(db, "pawn", SUBJECT)
    assert (
        pending["status"] == "needs_verification" and pending["verification"]["status"] == "pending"
    )
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pawn", "continue")["status"] == "correct"
    assert show(db, "pawn", SUBJECT)["pawn_continuation"]
    assert submit(db, "pawn", SUBJECT, event_id="answer", move="e3f3") == original
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
        ).fetchone()[0]
        == frozen
    )
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tracked
    } == before


def test_review_revocation_before_publication_cancels_pawn_verdict(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.objective_verify import compute

    db, evidence = setup_game(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence, "race")
    submit(db, "race", SUBJECT, event_id="move", move="e3f3")

    def revoke(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, SUBJECT, verifier=revoke)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "source_unavailable" and result["learning_eligible"] is False
