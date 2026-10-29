"""Build current owned mate practice snapshots with validated lines."""

from .decision_history import decision_board
from .mate_evidence import load
from .mate_inspection_source import position_row
from .mate_practice_lines import prepared_lines

VERSION = "mate-own-v1"


def resolve(db, version, key, subject):
    if (
        version != VERSION
        or not key.isdecimal()
        or not 0 < int(key) < 2**63
        or str(int(key)) != key
    ):
        raise ValueError("practice source unavailable")
    evidence, fact, fingerprint = load(db, int(key), subject)
    if evidence["review_status"] in {"rejected", "revoked"}:
        raise ValueError("practice source unavailable")
    position = position_row(db, evidence["position_id"])
    board = decision_board(db, position)
    lines = prepared_lines(board, fact["payload"]["proof"])
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (int(key),),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "checkmate",
        "lines": lines,
        "provenance": {
            "source_fingerprint": fingerprint,
            "evidence_id": int(key),
            "position_id": position["id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
        },
    }
