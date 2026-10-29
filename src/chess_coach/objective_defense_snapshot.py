"""Build the immutable immediate-defense snapshot."""

from .objective_contract import OWNED_HISTORY

OBJECTIVE = "avoid-immediate-mate-v1"


def snapshot(db, board, evidence, fact, fingerprint, text):
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "avoid_immediate_mate",
        "lines": [text],
        "provenance": {
            "source_fingerprint": fingerprint,
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
        },
    }
