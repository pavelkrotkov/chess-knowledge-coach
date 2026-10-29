"""Bound owned game bytes before parsing or replaying its history."""

from .learner_identity import normalize_identity

MAX_GAME_BYTES = 1_000_000


def within_budget(db, evidence_id, subject):
    row = db.connection.execute(
        "SELECT length(CAST(g.pgn AS BLOB)) FROM evidence_mappings e JOIN positions p ON p.id=e.position_id JOIN games g ON g.id=p.game_id WHERE e.id=? AND e.subject=?",
        (evidence_id, normalize_identity(subject)),
    ).fetchone()
    return row is not None and row[0] <= MAX_GAME_BYTES
