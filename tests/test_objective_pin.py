"""Owned pin practice preserves source-bound, limited proof and immutable results."""

import json
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.objective_pin_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_pin_pipeline import Engine

SUBJECT = "fixture_learner"
ABSOLUTE = "2k5/3r1N2/N1n1B2p/3P4/1Q6/8/8/1R1K4 w - - 0 1"
RELATIVE = "4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1"


def owned_pin(path, monkeypatch, *, black=False, relative=False, unknown_history=False):
    board = chess.Board(RELATIVE if relative else ABSOLUTE)
    move = chess.Move.from_uci("a6b5" if relative else "b4c4")
    if black:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    if unknown_history:
        board.halfmove_clock = 1
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
        }
    )
    node = game.add_variation(move)
    board.push(move)
    node.add_variation(next(iter(board.legal_moves)))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, SUBJECT, "execute")
    assert result["outcome"] == "success"
    return db, result["evidence_ids"][0]


def begin(db, evidence, attempt="pin"):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


@pytest.mark.parametrize("black", [False, True])
def test_alternative_pin_is_proved_without_rewriting_response_or_learning(
    tmp_path, monkeypatch, black
):
    db, evidence = owned_pin(tmp_path / "owned.sqlite", monkeypatch, black=black)
    before = {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in (
            "evidence_mappings",
            "evidence_review_events",
            "mastery_events",
            "mastery_states",
            "training_items",
            "training_attempts",
            "training_completions",
        )
    }
    state = begin(db, evidence)
    original = chess.Move.from_uci("b4c4")
    alternative = chess.Move.from_uci("b4c5")
    if black:
        original = chess.Move(
            chess.square_mirror(original.from_square), chess.square_mirror(original.to_square)
        )
        alternative = chess.Move(
            chess.square_mirror(alternative.from_square), chess.square_mirror(alternative.to_square)
        )
    assert original.uci() != alternative.uci()
    assert original.uci() not in json.dumps(state)
    answer = submit(db, "pin", SUBJECT, event_id="answer", move=alternative.uci())
    assert answer["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pin", "answer")["status"] == "correct"
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["proof"]["type"] == "absolute_pin"
    assert result["proof"]["move"] == alternative.uci()
    assert result["proof"]["pinner"] != state["pin_attacker"]
    assert show(db, "pin", SUBJECT)["verification"]["status"] == "correct"
    assert submit(db, "pin", SUBJECT, event_id="answer", move=alternative.uci()) == answer
    assert {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in before
    } == before


def test_publication_rechecks_review_after_computation(tmp_path, monkeypatch):
    import time

    from chess_coach.objective_publication import publish
    from chess_coach.objective_verify import compute

    db, evidence = owned_pin(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence)
    original = submit(db, "pin", SUBJECT, event_id="answer", move="b4c5")
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    computed = compute(db, request, time.monotonic)
    assert computed["status"] == "correct"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    result = publish(db, request, computed)
    assert result["status"] == "unresolved" and result["reason"] == "source_unavailable"
    assert (
        json.loads(
            db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        )
        == original
    )
    assert publish(db, request, computed) == result
