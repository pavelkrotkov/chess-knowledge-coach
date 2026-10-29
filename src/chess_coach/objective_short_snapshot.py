"""Build an immutable source snapshot with one proven root."""

from .mate_practice_lines import prepared_lines

OBJECTIVE = "mate-within-two-v1"


def snapshot(db, board, evidence, fact, fingerprint):
    lines = prepared_lines(board, fact["payload"]["proof"])
    selected = _select(lines)
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "mate_within_two",
        "lines": selected,
        "provenance": {
            "source_fingerprint": fingerprint,
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "objective_version": OBJECTIVE,
            "history_mode": "owned_historical",
        },
    }


def _select(lines):
    long_lines = [line for line in lines if len(line.split()) == 3]
    if not long_lines:
        raise ValueError("mate-within-two source unavailable")
    root = min(line.split()[0] for line in long_lines)
    return [line for line in long_lines if line.split()[0] == root]
