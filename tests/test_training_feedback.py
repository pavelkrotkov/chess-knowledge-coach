"""Verified puzzle completion, review policy and atomic scheduling."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import chess
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.puzzle_sessions import request_hint, start_attempt
from chess_coach.training import create_training_item
from chess_coach.training_feedback import (
    puzzle_training_ref,
    show_training_puzzle,
    submit_training_move,
)

MATE_FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"
MATE_LINE = "g8h8 c5f8"


def setup_attempt(path=":memory:", *, fen=MATE_FEN, solution=MATE_LINE, skill="mate_in_one"):
    db = Database(path)
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES ('v1','fixture','checksum')"
    )
    db.connection.execute(
        """INSERT INTO puzzles
        (puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES ('p1',1,?,'',?,1200,80,'[]','fixture')""",
        (fen, solution),
    )
    db.connection.commit()
    start_attempt(db, attempt_id="a1", version="v1", puzzle_id="p1")
    item = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref("v1", "p1"),
        skill=skill,
        operation="execute",
    )
    return db, item


def submit(db, item, *, move="c5c8", event="move1", subject="Learner"):
    return submit_training_move(db, "a1", event_id=event, move=move, item_id=item, subject=subject)


def test_verified_mate_completion_is_atomic_linked_unreviewed_and_idempotent():
    db, item = setup_attempt()
    response = submit(db, item)
    training = response["training"]
    assert response["status"] == "solved"
    assert training["rating"] == "good" and training["evidence_reason"] == "verified_mate_in_one"
    evidence = db.connection.execute("SELECT * FROM evidence_mappings").fetchone()
    assert (evidence["position_id"], evidence["mapping_run_id"]) == (None, None)
    assert (evidence["skill"], evidence["operation"], evidence["outcome"]) == (
        "mate_in_one",
        "execute",
        "success",
    )
    assert evidence["source_provenance"] == "training_attempt" and evidence["subject"] == "learner"
    assert (
        evidence["human_validated"] == 0 and evidence["observation_at"] == response["finished_at"]
    )
    context = json.loads(evidence["context_json"])
    assert context["played_move"] == "c5c8" and context["played_checkmate"] is True
    completion = db.connection.execute("SELECT * FROM training_completions").fetchone()
    assert completion["evidence_id"] == evidence["id"] == training["evidence_id"]
    attempt = db.connection.execute("SELECT * FROM training_attempts").fetchone()
    assert completion["training_attempt_id"] == attempt["id"] == training["attempt_id"]
    assert attempt["elapsed_seconds"] is None and attempt["reviewed_at"] == response["finished_at"]
    assert completion["policy_version"] and completion["mapper_version"]
    review_evidence(db, evidence["id"], decision="accept", actor="fixture-reviewer")
    assert submit(db, item, subject=" LEARNER ") == response
    assert inspect_evidence(db, evidence["id"])["review_status"] == "accepted"
    for table in (
        "puzzle_session_events",
        "training_completions",
        "training_attempts",
        "evidence_mappings",
    ):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1
    with pytest.raises(ValueError, match="different request"):
        submit(db, item, event="another")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE training_completions SET evidence_reason='changed'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE puzzle_sessions SET initial_fen='changed'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE puzzle_session_events SET submitted_move='changed'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE training_attempts SET rating='again'")
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_hint_solved_schedules_hard_without_evidence():
    db, item = setup_attempt()
    request_hint(db, "a1", event_id="hint")
    result = submit(db, item)
    assert result["training"]["rating"] == "hard"
    assert result["training"]["evidence_id"] is None
    assert result["training"]["evidence_reason"] == "hint_used"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_failed_move_schedules_again_without_evidence():
    db, item = setup_attempt(fen=chess.STARTING_FEN, solution="e2e4 e7e5")
    result = submit(db, item, move="d7d5")
    assert result["status"] == "failed"
    assert result["training"]["rating"] == "again"
    assert result["training"]["evidence_reason"] == "failed_attempt"
    assert result["training"]["evidence_id"] is None


def test_nonmate_success_is_not_inferred_as_skill_evidence():
    db, item = setup_attempt(fen=chess.STARTING_FEN, solution="e2e4 e7e5")
    result = submit(db, item, move="e7e5")
    assert result["status"] == "solved" and result["training"]["rating"] == "good"
    assert result["training"]["evidence_reason"] == "unsupported_puzzle_decision"
    assert result["training"]["evidence_id"] is None


def test_illegal_move_is_not_completion_and_retry_is_stable():
    db, item = setup_attempt()
    result = submit(db, item, move="bad", event="illegal")
    assert result["status"] == "active" and result["feedback"] == "illegal"
    assert submit(db, item, move="bad", event="illegal") == result
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert submit(db, item)["status"] == "solved"


def test_unsupported_item_skill_never_generates_evidence():
    db, item = setup_attempt(skill="fork")
    result = submit(db, item)
    assert result["training"]["evidence_reason"] == "unsupported_training_skill"
    assert result["training"]["evidence_id"] is None


@pytest.mark.parametrize(
    "point", ["record_evidence", "review_item_in_transaction", "save_completion"]
)
def test_injected_failures_roll_back_terminal_event_and_all_feedback(monkeypatch, point):
    from chess_coach import training_feedback_finish

    db, item = setup_attempt()
    original = getattr(training_feedback_finish, point)

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected")

    monkeypatch.setattr(training_feedback_finish, point, fail)
    with pytest.raises(RuntimeError, match="injected"):
        submit(db, item)
    assert db.connection.execute("SELECT status FROM puzzle_sessions").fetchone()[0] == "active"
    for table in (
        "puzzle_session_events",
        "training_completions",
        "training_attempts",
        "evidence_mappings",
    ):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert db.connection.execute("SELECT last_review FROM training_items").fetchone()[0] is None
    monkeypatch.setattr(training_feedback_finish, point, original)
    assert submit(db, item)["status"] == "solved"


def test_wrong_puzzle_item_and_missing_subject_fail_before_event():
    db, item = setup_attempt()
    other = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref("v1", "other"),
        skill="mate_in_one",
        operation="execute",
    )
    other_version = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref("v2", "p1"),
        skill="mate_in_one",
        operation="execute",
    )
    for wrong_item in (other, other_version):
        with pytest.raises(ValueError, match="does not match"):
            submit(db, wrong_item)
    with pytest.raises(ValueError, match="explicit learner"):
        submit(db, item, subject="default")
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0


def test_caller_transaction_can_roll_back_complete_batch():
    db, item = setup_attempt()
    db.connection.execute("BEGIN")
    assert submit(db, item)["status"] == "solved"
    assert db.connection.in_transaction
    db.connection.rollback()
    assert db.connection.execute("SELECT status FROM puzzle_sessions").fetchone()[0] == "active"
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_backward_scheduler_review_rejects_completion_without_partial_data():
    db, item = setup_attempt()
    db.connection.execute(
        "UPDATE training_items SET last_review='2999-01-01T00:00:00+00:00' WHERE id=?", (item,)
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="previous review"):
        submit(db, item)
    assert db.connection.execute("SELECT status FROM puzzle_sessions").fetchone()[0] == "active"
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0


def test_schema_upgrade_preserves_existing_sessions_and_rolls_back_on_failure(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_training_completions", lambda connection: None)
        patch.setattr(db_recent, "add_curriculum_index", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=11")
    db.connection.execute("""INSERT INTO puzzle_sessions
        (attempt_id,corpus_version,corpus_checksum,puzzle_id,initial_fen,solution,
         current_fen,next_index,status,hints_used,started_at)
        VALUES ('old','v1','checksum','p1','fen','line','fen',1,'active',0,'2025-01-01T00:00:00+00:00')""")
    db.connection.commit()
    before = tuple(db.connection.execute("SELECT * FROM puzzle_sessions").fetchone())
    original = db_recent.add_training_completions

    def fail(connection):
        original(connection)
        raise RuntimeError("injected migration")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_training_completions", fail)
        with pytest.raises(RuntimeError, match="injected migration"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 11
    assert (
        db.connection.execute(
            "SELECT name FROM sqlite_master WHERE name='training_completions'"
        ).fetchone()
        is None
    )
    db.initialize()
    assert tuple(db.connection.execute("SELECT * FROM puzzle_sessions").fetchone()) == before
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_concurrent_identical_terminal_request_completes_once(tmp_path):
    path = tmp_path / "training.sqlite"
    db, item = setup_attempt(path)
    db.close()

    def run():
        connection = Database(path)
        try:
            return submit(connection, item)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: run(), range(2)))
    assert first == second
    db = Database(path)
    for table in (
        "puzzle_session_events",
        "training_completions",
        "training_attempts",
        "evidence_mappings",
    ):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1


def test_nonterminal_training_result_does_not_disclose_future_solution():
    db, item = setup_attempt(fen=chess.STARTING_FEN, solution="e2e4 e7e5 g1f3 b8c6")
    first = submit(db, item, move="e7e5")
    assert first["status"] == "active" and first["opponent_move"] == "g1f3"
    assert "b8c6" not in json.dumps(first)
    assert "training" not in first
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    done = submit(db, item, move="b8c6", event="move2")
    assert done["status"] == "solved" and done["training"]["evidence_id"] is None


def test_completion_rejects_different_subject_on_retry():
    db, item = setup_attempt()
    submit(db, item, subject="Learner")
    with pytest.raises(ValueError, match="different request"):
        submit(db, item, subject="Other Learner")
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 1


@pytest.mark.parametrize("bad_item", [True, 0, -1, "1"])
def test_invalid_item_id_is_rejected_before_any_event(bad_item):
    db, _ = setup_attempt()
    with pytest.raises(ValueError, match="positive integer"):
        submit_training_move(
            db, "a1", event_id="move", move="c5c8", item_id=bad_item, subject="learner"
        )
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_session_events").fetchone()[0] == 0


def test_declared_mate_task_nonmate_failure_is_unreviewed_evidence():
    db, item = setup_attempt()
    prompt = show_training_puzzle(db, "a1", item_id=item)
    assert prompt["training_objective"] == "Find mate in one."
    assert "c5f8" not in json.dumps(prompt) and "c5c8" not in json.dumps(prompt)
    result = submit(db, item, move="c5a5")
    assert result["status"] == "failed"
    assert result["training"]["evidence_reason"] == "missed_mate_in_one"
    assert result["training"]["rating"] == "again"
    evidence = db.connection.execute("SELECT * FROM evidence_mappings").fetchone()
    assert (evidence["skill"], evidence["operation"], evidence["outcome"]) == (
        "mate_in_one",
        "execute",
        "failure",
    )
    assert evidence["human_validated"] == 0 and evidence["source_provenance"] == "training_attempt"
    assert evidence["position_id"] is None and evidence["mapping_run_id"] is None
    context = json.loads(evidence["context_json"])
    assert context["played_checkmate"] is False and context["mating_moves"]
    assert context["training_objective"] == "Find mate in one."
    assert context["mapper_version"] == "verified-puzzle-mate-v2"
    assert submit(db, item, move="c5a5") == result
    assert inspect_evidence(db, evidence["id"])["review_status"] == "unreviewed"
    review_evidence(db, evidence["id"], decision="accept", actor="fixture-reviewer")
    assert submit(db, item, move="c5a5") == result
    assert inspect_evidence(db, evidence["id"])["review_status"] == "accepted"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1


def test_hint_followed_by_failed_mate_does_not_produce_failure_evidence():
    db, item = setup_attempt()
    request_hint(db, "a1", event_id="hint")
    result = submit(db, item, move="c5a5")
    assert result["status"] == "failed"
    assert result["training"]["evidence_reason"] == "hint_used"
    assert result["training"]["evidence_id"] is None


def test_multistep_failure_is_not_inferred_from_mate_prompt():
    db, item = setup_attempt(fen=chess.STARTING_FEN, solution="e2e4 e7e5 g1f3 b8c6")
    assert show_training_puzzle(db, "a1", item_id=item)["training_objective"] is None
    assert submit(db, item, move="e7e5")["status"] == "active"
    result = submit(db, item, move="g8f6", event="move2")
    assert result["status"] == "failed"
    assert result["training"]["evidence_reason"] == "unsupported_puzzle_decision"
    assert result["training"]["evidence_id"] is None
