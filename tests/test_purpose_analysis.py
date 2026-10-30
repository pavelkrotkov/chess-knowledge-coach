"""Synthetic purpose diagnostic coverage."""

import sqlite3

import pytest

from chess_coach.deep_selection import select_deep
from chess_coach.evidence_review import review_evidence
from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_fixtures import configure, request
from tests.purpose_observation import assert_candidate_search, snapshot_learning_tables
from tests.purpose_ui_assertions import assert_private_browser
from tests.test_deep_selection import LEARNER, setup_game


def test_owned_candidate_search_is_separate_and_browser_read_only(tmp_path, monkeypatch):
    path = tmp_path / "purpose.sqlite"
    db = setup_game(path, monkeypatch)
    select_deep(db, [1], learner=LEARNER, per_game=2, total=2)
    before = snapshot_learning_tables(db)
    request_id = request(db)
    assert request(db) == request_id
    engine = configure(monkeypatch, db)
    result = run(db, request_id, LEARNER)
    assert result["status"] == "complete" and result["detail"] == "comparable"
    assert_candidate_search(engine, db, request_id)
    assert before == snapshot_learning_tables(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("UPDATE purpose_analysis_attempts SET detail=?", ("changed",))
    db.connection.rollback()
    assert_private_browser(path, request_id)
    assert before == snapshot_learning_tables(db)


def test_unrelated_review_does_not_turn_diagnostic_into_learning(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "review.sqlite", monkeypatch)
    request_id = request(db)
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER)["status"] == "complete"
    before = show(db, request_id, LEARNER)
    cursor = db.connection.execute(
        "INSERT INTO evidence_mappings(position_id,skill,operation,outcome,confidence) VALUES(?,?,?,?,?)",
        (1, "synthetic", "observe", "ambiguous", 0.5),
    )
    db.connection.commit()
    review_evidence(db, cursor.lastrowid, decision="accept", actor="synthetic")
    assert show(db, request_id, LEARNER) == before
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    assert "no evidence" in before["boundary"]
