"""Owned anchored fork defenses receive independently queued verdicts."""

from chess_coach.fork_defense_detector import process_decision
from chess_coach.objective_fork_defense_contract import VERSION
from chess_coach.unified_sessions import start
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
