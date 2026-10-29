"""Resolve current owned back-rank practice snapshots."""

from .back_rank_evidence import load
from .back_rank_practice_lines import lines
from .decision_history import decision_board
from .mate_inspection_source import position_row

VERSION = "back-rank-own-v1"


def resolve(db, version, key, subject):
    if not _valid_key(version, key):
        raise ValueError("back-rank practice unavailable")
    evidence, fact, fingerprint = load(db, int(key), subject)
    if evidence["review_status"] in {"rejected", "revoked"}:
        raise ValueError("back-rank practice unavailable")
    position = position_row(db, evidence["position_id"])
    board = decision_board(db, position)
    prepared = lines(board, fact["payload"], evidence["operation"])
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (int(key),),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "back_rank_defense" if evidence["operation"] == "prevent" else "checkmate",
        "lines": prepared,
        "provenance": {
            "source_fingerprint": fingerprint,
            "evidence_id": int(key),
            "position_id": position["id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
        },
    }


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
