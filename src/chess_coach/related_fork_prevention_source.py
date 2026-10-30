"""Resolve a current pre-existing anchored knight-fork defense source."""

import chess

from .decision_history import decision_board
from .fork_defense_contract import VERSION
from .fork_defense_probe import hypothetical
from .mate_inspection_source import position_row
from .material_opportunity_source import load_source
from .related_capture_source import _opening
from .related_fork_prevention_roles import describe
from .related_fork_prevention_source_current import current
from .related_fork_prevention_source_witness import branch


def source_for_evidence(db, subject, evidence_id):
    try:
        return _load(db, subject, evidence_id)
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ValueError("fork prevention source unavailable or stale") from None


def _load(db, subject, evidence_id):
    evidence = current(db, subject, evidence_id)
    fact = evidence["facts"][0]
    payload = fact["payload"]
    board = decision_board(db, position_row(db, evidence["position_id"]))
    proof, anchored, defense = branch(board, payload)
    candidates = hypothetical(board)
    if candidates is None or candidates.get(proof["move"]) != [
        chess.parse_square(s) for s in proof["targets"]
    ]:
        raise ValueError("pre-existing threat unavailable")
    source = load_source(db, fact["detector_run_id"])
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence_id,),
    ).fetchone()
    return {
        "prompt_fen": evidence["decision_fen"],
        "learner_color": "white" if board.turn else "black",
        "lines": [
            " ".join(payload["played" if payload["outcome"] == "success" else "best"]["uci"])
        ],
        "opening": _opening(db, evidence["position_id"]),
        "outcome": evidence["outcome"],
        "features": describe(board, defense, anchored, proof),
        "provenance": {
            "evidence_id": evidence_id,
            "position_id": evidence["position_id"],
            "source_fingerprint": source["source_marker"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "fact_id": fact["id"],
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": VERSION,
            "threat_origin": "positional_before_played",
        },
    }
