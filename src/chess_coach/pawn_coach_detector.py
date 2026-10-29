"""Compute and atomically publish bounded pawn observations from current sources."""

from .pawn_coach_contract import PRODUCER
from .pawn_coach_publish import publish
from .pawn_coach_source import prepare


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("pawn detection requires an idle database")
    prepared = prepare(db, position_id, learner)
    if prepared["fact"] is None and not _has_prior(db, position_id):
        return {"replayed": False, "skipped": True, "outcome": "unsupported"}
    return publish(db, prepared, learner)


def _has_prior(db, position_id):
    return (
        db.connection.execute(
            "SELECT 1 FROM detector_runs WHERE position_id=? AND producer=? AND status='active'",
            (position_id, PRODUCER),
        ).fetchone()
        is not None
    )
