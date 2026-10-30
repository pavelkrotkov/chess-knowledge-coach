"""Owned anchored fork defenses receive independently queued verdicts."""

import json

import pytest

from chess_coach.fork_defense_detector import process_decision
from chess_coach.objective_fork_defense_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.related_protection_support import learning_counts
from tests.test_fork_defense import mirror
from tests.test_fork_defense_pipeline import LEARNER, make_game


def fixture(path, monkeypatch, *, black=False, failure=False):
    db, _ = make_game(path, monkeypatch, black=black, failure=failure)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    return db, evidence


def begin(db, evidence, attempt="fork-defense"):
    return start(
        db,
        attempt_id=attempt,
        subject=LEARNER,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_owned_defense_is_queued_and_verified_for_each_source_origin(
    tmp_path, monkeypatch, black, failure
):
    db, evidence = fixture(
        tmp_path / "fork-defense.sqlite", monkeypatch, black=black, failure=failure
    )
    before = learning_counts(db)
    state = begin(db, evidence)
    good = mirror("a1b1") if black else "a1b1"
    assert state["objective"] == "avoid_anchored_knight_fork"
    assert state["review_status"] == "unreviewed"
    assert good not in json.dumps(state)
    event = submit(db, "fork-defense", LEARNER, event_id="answer", move=good)
    assert event["status"] == event["feedback"] == "needs_verification"
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    result = inspect(db, LEARNER, "fork-defense", "answer")
    assert result["status"] == "correct"
    assert show(db, "fork-defense", LEARNER)["verification"]["status"] == "correct"
    assert submit(db, "fork-defense", LEARNER, event_id="answer", move=good) == event
    assert learning_counts(db) == before
    db.close()
