"""Synthetic current-source pawn coaching, with independently closed mastery."""

from datetime import UTC, datetime

import chess
import pytest

from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pawn_coach_observation import observe
from chess_coach.pawn_coach_worker import process_pawns
from chess_coach.pawn_practice import VERSION
from chess_coach.pawn_practice_list import list_candidates
from chess_coach.pawn_proof import inspect
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_mate_proof import owned_game

FEN = "8/8/8/8/2k5/4K3/3P4/8 w - - 0 1"


@pytest.fixture(scope="module")
def proof():
    result = inspect(chess.Board(FEN))
    assert result["lower"] == result["upper"] == 1
    return result


@pytest.fixture
def game(tmp_path, monkeypatch, proof):
    db = owned_game(tmp_path / "pawn.sqlite", monkeypatch, fen=FEN, move="d4")
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    return db


def test_real_proof_classifies_winning_choice_and_mistake(proof):
    assert observe(proof, "e3e4")["outcome"] == "success"
    assert observe(proof, "d2d4")["outcome"] == "failure"
    assert observe(proof, "e3f4")["outcome"] == "ambiguous"
    forced_loss = {**proof, "lower": -1, "upper": -1}
    assert observe(forced_loss, "d2d4")["outcome"] == "ambiguous"
    equal = {**proof, "alternatives": [proof["alternatives"][0]]}
    assert observe(equal, "d2d4")["outcome"] == "ambiguous"


def test_worker_evidence_review_practice_and_mastery_gate(game):
    report = process_pawns(
        game, PipelineConfig(learner="fixture_a", pawn_max_scan=2, pawn_max_decisions=1)
    )
    assert report["outcomes"] == {"failure": 1}
    row = game.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='king_pawn_endgame'"
    ).fetchone()
    evidence_id = row["id"]
    evidence = inspect_evidence(game, evidence_id)
    assert evidence["pawn_source_currentness"] == "current"
    assert evidence["review_status"] == "unreviewed"
    assert evidence["pawn_explanation"]["preserving"] == ["Ke4"]
    assert game.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    candidates = list_candidates(game, "fixture_a")
    assert candidates["candidates"][0]["key"] == str(evidence_id)
    session = start(
        game,
        attempt_id="one",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    assert session["objective"] == "pawn_win" and "source_key" not in session
    complete = submit(game, "one", "fixture_a", event_id="m1", move="e3e4")
    assert complete["status"] == "line_completed"
    assert game.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1
    start(
        game,
        attempt_id="two",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    unknown = submit(game, "two", "fixture_a", event_id="m2", move="e3f4")
    assert unknown["status"] == "needs_verification"
    review_evidence(game, evidence_id, decision="accept", actor="fixture_reviewer")
    items, exclusions = eligible_contexts(
        game, "fixture_a", "king_pawn_endgame", "execute", datetime.now(UTC)
    )
    assert not items and exclusions.get("pawn_family_unvalidated") == 1
    with pytest.raises(ValueError, match="stale"):
        show(game, "one", "fixture_a")
