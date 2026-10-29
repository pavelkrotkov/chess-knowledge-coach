"""Synthetic current-source pawn coaching, with independently closed mastery."""

import sys
from datetime import UTC, datetime

import chess
import httpx
import pytest

from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pawn_coach_detector import process_decision
from chess_coach.pawn_coach_observation import observe
from chess_coach.pawn_coach_worker import process_pawns
from chess_coach.pawn_mastery_policy import mastery_allowed
from chess_coach.pawn_practice import VERSION, resolve
from chess_coach.pawn_practice_list import list_candidates
from chess_coach.pawn_proof import inspect
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
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


def test_promotion_colors_and_equivalent_choices():
    board = chess.Board("7k/P1K5/8/8/8/8/8/8 w - - 0 1")
    for position in (board, board.mirror()):
        result = inspect(position, node_limit=100, max_plies=2)
        pawn = "a7a8" if position.turn else "a2a1"
        assert observe(result, pawn + "q")["outcome"] == "success"
        assert observe(result, pawn + "r")["outcome"] == "success"
        assert observe(result, pawn + "n")["outcome"] == "failure"
        assert observe(result, pawn + "b")["outcome"] == "failure"
        equal_only = {
            **result,
            "alternatives": [
                item for item in result["alternatives"] if item["lower"] == item["upper"] == 1
            ],
        }
        assert len(equal_only["alternatives"]) >= 2
        assert observe(equal_only, pawn + "q")["outcome"] == "ambiguous"


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


def test_proof_change_reactivates_without_inheriting_review(game, monkeypatch, proof):
    first = process_decision(game, 1, "fixture_a")
    old = first["evidence_ids"][0]
    review_evidence(game, old, decision="accept", actor="fixture_reviewer")
    monkeypatch.setattr(
        "chess_coach.pawn_inspection.inspect",
        lambda board: {"status": "unknown", "reason": "node_limit"},
    )
    middle = process_decision(game, 1, "fixture_a")
    assert middle["outcome"] == "ambiguous" and middle["evidence_ids"] != [old]
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    new = process_decision(game, 1, "fixture_a")
    assert new["evidence_ids"] != [old] and new["evidence_ids"] != middle["evidence_ids"]
    assert inspect_evidence(game, new["evidence_ids"][0])["review_status"] == "unreviewed"
    assert inspect_evidence(game, old)["lifecycle_status"] == "superseded"
    assert (
        game.connection.execute(
            "SELECT COUNT(*) FROM evidence_review_events WHERE evidence_id=?", (old,)
        ).fetchone()[0]
        == 1
    )


def test_family_gate_closes_renamed_producers_and_cross_skill_links(game):
    result = process_decision(game, 1, "fixture_a")
    evidence_id = result["evidence_ids"][0]
    base = {
        "id": evidence_id,
        "skill": "king_pawn_endgame",
        "mapping_producer": "renamed",
        "link_count": 1,
    }
    assert not mastery_allowed(game, base)
    assert not mastery_allowed(game, {**base, "skill": "promotion"})
    assert not mastery_allowed(game, {**base, "skill": "other"})
    assert mastery_allowed(game, {**base, "skill": "other", "link_count": 0})


def test_stale_source_and_revocation_hide_practice(game):
    item = process_decision(game, 1, "fixture_a")
    evidence_id = item["evidence_ids"][0]
    start(
        game,
        attempt_id="stale",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    review_evidence(game, evidence_id, decision="reject", actor="fixture_reviewer")
    assert not list_candidates(game, "fixture_a")["candidates"]
    with pytest.raises(ValueError, match="stale"):
        show(game, "stale", "fixture_a")
    game.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    game.connection.commit()
    assert inspect_evidence(game, evidence_id)["pawn_source_currentness"] == "stale"


def test_both_color_mirrored_success(proof):
    mirrored = inspect(chess.Board(FEN).mirror())
    assert observe(mirrored, "e6e5")["outcome"] == "success"
    assert observe(mirrored, "d7d5")["outcome"] == "failure"


def test_browser_lists_provisional_and_review_shows_verified_line(game):
    evidence_id = process_decision(game, 1, "fixture_a")["evidence_ids"][0]
    app = create_app(
        db_path=game.path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200
    assert b"Provisional pawn-endgame practice" in library.data
    assert b"cannot contribute to mastery" in library.data
    assert b"Ke4" not in library.data
    detail = client.get(
        f"/evidence/{evidence_id}", base_url="https://coach.invalid", headers=headers
    )
    assert (
        detail.status_code == 200
        and b"Ke4" in detail.data
        and b"does not establish intent or mastery" in detail.data
    )


def test_missing_resource_is_ambiguous_and_not_practice(game, monkeypatch):
    monkeypatch.setattr(
        "chess_coach.pawn_inspection.inspect",
        lambda board: {"status": "unknown", "reason": "proof_resources_unavailable"},
    )
    monkeypatch.setattr("chess_coach.pawn_coach_publish.open_verified", lambda: None)
    result = process_decision(game, 1, "fixture_a")
    evidence = inspect_evidence(game, result["evidence_ids"][0])
    assert evidence["outcome"] == "ambiguous"
    assert (
        evidence["context"]["pawn_observation"]["proof"]["reason"] == "proof_resources_unavailable"
    )
    assert not list_candidates(game, "fixture_a")["candidates"]


def test_replay_preserves_one_review_and_source_mismatch_prevents_write(game, monkeypatch):
    original = process_decision(game, 1, "fixture_a")
    review_evidence(game, original["evidence_ids"][0], decision="accept", actor="fixture_reviewer")
    replay = process_decision(game, 1, "fixture_a")
    assert replay["replayed"] and replay["evidence_ids"] == original["evidence_ids"]
    assert inspect_evidence(game, replay["evidence_ids"][0])["review_status"] == "accepted"
    monkeypatch.setattr("chess_coach.pawn_coach_publish._still_current", lambda *args: False)
    with pytest.raises(ValueError, match="source changed"):
        process_decision(game, 1, "fixture_a")
    assert (
        game.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer='pawn-endgame-observation'"
        ).fetchone()[0]
        == 1
    )


def test_worker_budget_cursor_is_separate_and_replays(game):
    config = PipelineConfig(learner="fixture_a", pawn_max_scan=1, pawn_max_decisions=1)
    first = process_pawns(game, config)
    second = process_pawns(game, config)
    assert first["processed"] == second["processed"] == 1
    assert second["replayed"] == 1
    rows = game.connection.execute("SELECT scan_hash FROM pipeline_cursors").fetchall()
    assert any(row["scan_hash"] == "pawn-coach-worker-v1" for row in rows)


def test_automatic_pipeline_runs_pawn_worker_without_external_engine(game):
    config = PipelineConfig(
        learner="fixture_a",
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_enabled=False,
        pawn_max_scan=2,
        pawn_max_decisions=1,
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    report = process_pipeline(game, config, transport=transport)
    assert report["pawns"]["outcomes"] == {"failure": 1}
    assert (
        game.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings WHERE skill='king_pawn_endgame'"
        ).fetchone()[0]
        == 1
    )


def test_incomplete_custom_fen_history_is_ambiguous(tmp_path, monkeypatch):
    fen = "8/8/8/8/8/8/4P3/K6k w - - 99 1"
    db = owned_game(tmp_path / "history.sqlite", monkeypatch, fen=fen, move="e4")
    result = process_decision(db, 1, "fixture_a")
    assert result["outcome"] == "ambiguous"
    evidence = inspect_evidence(db, result["evidence_ids"][0])
    assert (
        evidence["context"]["pawn_observation"]["proof"]["reason"]
        == "incomplete_repetition_history"
    )
    assert not list_candidates(db, "fixture_a")["candidates"]


def test_worker_unavailable_attempts_count_against_budget(game, monkeypatch):
    def unavailable(*args):
        raise ValueError("synthetic unavailable")

    monkeypatch.setattr("chess_coach.pawn_coach_worker_item.process_decision", unavailable)
    result = process_pawns(
        game, PipelineConfig(learner="fixture_a", pawn_max_scan=40, pawn_max_decisions=1)
    )
    assert result["examined"] == result["unavailable"] == 1
    assert result["status"] == "partial"


def test_practice_keys_are_bounded_and_subject_owned(game):
    evidence_id = process_decision(game, 1, "fixture_a")["evidence_ids"][0]
    for key in ("9" * 256, "\uff10\uff11", "0", "-1", "01"):
        with pytest.raises(ValueError, match="unavailable"):
            resolve(game, key, "fixture_a")
    with pytest.raises(ValueError, match="unavailable"):
        resolve(game, str(evidence_id), "fixture_b")


def test_renamed_mapper_and_relabelled_pawn_fact_cannot_bypass_mastery(game):
    pawn = process_decision(game, 1, "fixture_a")
    other_fact = record_fact_run(
        game,
        position_id=1,
        producer="other-detector",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "other", "payload": {}}],
    )
    for skill, fact_id in (
        ("promotion", other_fact["fact_ids"][0]),
        ("other_skill", pawn["fact_ids"][0]),
    ):
        with mapping_transaction(game):
            mapped = record_mapping_run_in_transaction(
                game,
                position_id=1,
                producer="renamed-producer",
                mapper_version="v1",
                subject="fixture_a",
                operation="execute",
                scope_key=skill,
                input_data={},
                mappings=[
                    {
                        "skill": skill,
                        "outcome": "success",
                        "confidence": 1.0,
                        "fact_ids": [fact_id],
                        "context": {},
                        "observation_at": None,
                    }
                ],
            )
        review_evidence(
            game, mapped["evidence_ids"][0], decision="accept", actor="fixture_reviewer"
        )
        selected, exclusions = eligible_contexts(
            game, "fixture_a", skill, "execute", datetime.now(UTC)
        )
        assert not selected and exclusions.get("pawn_family_unvalidated") == 1


def test_pawn_race_double_push_and_rule_of_square_exception():
    board = chess.Board("8/8/8/8/8/8/P3k3/K7 w - - 0 1")
    for position in (board, board.mirror()):
        report = inspect(position, node_limit=40, max_plies=1)
        single, double = ("a2a3", "a2a4") if position.turn else ("a7a6", "a7a5")
        assert observe(report, double)["outcome"] == "success"
        assert observe(report, single)["outcome"] == "failure"


def test_aligned_kings_do_not_determine_outcome_or_good_move():
    board = chess.Board("8/8/8/8/8/K7/P7/k7 w - - 0 1")
    for position in (board, board.mirror()):
        report = inspect(position)
        assert report["geometry"]["king_alignment"]
        assert not report["geometry"]["direct_opposition"]
        good, bad = ("a3b3", "a3a4") if position.turn else ("a6b6", "a6a5")
        assert observe(report, good)["outcome"] == "success"
        assert observe(report, bad)["outcome"] == "failure"


def test_direct_opposition_king_choice_is_proved_for_both_colors():
    board = chess.Board("8/1K6/P7/1k6/8/8/8/8 w - - 0 1")
    for position in (board, board.mirror()):
        report = inspect(position)
        assert report["geometry"]["direct_opposition"]
        good, bad = ("b7a7", "b7a8") if position.turn else ("b2a2", "b2a1")
        assert observe(report, good)["outcome"] == "success"
        assert observe(report, bad)["outcome"] == "failure"


def test_pawn_runs_do_not_supersede_another_producer(game, monkeypatch):
    other = record_fact_run(
        game,
        position_id=1,
        producer="unrelated-detector",
        detector_version="1",
        input_data={"source": "synthetic"},
        facts=[{"fact_type": "other", "payload": {}}],
    )
    process_decision(game, 1, "fixture_a")
    monkeypatch.setattr(
        "chess_coach.pawn_inspection.inspect",
        lambda board: {"status": "unknown", "reason": "node_limit"},
    )
    process_decision(game, 1, "fixture_a")
    row = game.connection.execute(
        "SELECT status FROM detector_runs WHERE id=?", (other["run_id"],)
    ).fetchone()
    assert row["status"] == "active"
