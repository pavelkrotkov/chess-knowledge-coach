"""Bind the exact owned source, review and created-fork witness."""

from .fork_defense_contract import VERSION
from .material_opportunity_source import load_source
from .related_capture_source import _opening
from .related_fork_avoidance_roles import describe_choice


def result(db, evidence, fact, board, good, bad, after_bad, proof):
    source = load_source(db, fact["detector_run_id"])
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": evidence["decision_fen"],
        "learner_color": "white" if board.turn else "black",
        "lines": [" ".join(fact["payload"]["best"]["uci"])],
        "opening": _opening(db, evidence["position_id"]),
        "outcome": evidence["outcome"],
        "features": describe_choice(board, good, bad, after_bad, proof),
        "source_counterfactual": {"bad_move": bad.uci(), "fork": proof},
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "source_fingerprint": source["source_marker"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "fact_id": fact["id"],
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": VERSION,
            "threat_origin": "created_by_played_move",
        },
    }
