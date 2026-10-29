"""Owned fork objectives verify equivalent moves without inventing game results."""

import json

import pytest

from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from tests.objective_fork_support import SUBJECT, begin, owned_fork


@pytest.mark.parametrize("played,outcome", [("f6g5", "failure"), ("b5c7", "success")])
def test_unlisted_owned_fork_is_proved_for_success_and_miss(tmp_path, monkeypatch, played, outcome):
    db, evidence = owned_fork(tmp_path / "fork.sqlite", monkeypatch, played)
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
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
    assert state["source_outcome"] == outcome
    assert state["fork_attacker"] == "b5" and state["fork_anchor"] == "e8"
    assert "b5c7" not in json.dumps(state) and "b5d6" not in json.dumps(state)
    original = submit(db, "fork", SUBJECT, event_id="answer", move="b5d6")
    assert original["status"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "fork", "answer")["status"] == "correct"
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["status"] == "correct" and result["proven_gain_floor"] == 3
    assert result["proof"]["targets"] == ["f5", "e8"]
    assert show(db, "fork", SUBJECT)["verification"]["status"] == "correct"
    assert submit(db, "fork", SUBJECT, event_id="answer", move="b5d6") == original
    assert {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    } == before
