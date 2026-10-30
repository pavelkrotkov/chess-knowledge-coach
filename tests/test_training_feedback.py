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
