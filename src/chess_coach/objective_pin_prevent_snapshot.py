"""Create an immutable source, witness, and bounded prevention snapshot."""

from .objective_contract import OWNED_HISTORY
from .objective_pin_prevent_contract import GOAL, OBJECTIVE
from .objective_pin_prevent_origin import binding


def snapshot(board, evidence, fact, source, budget):
    payload = fact["payload"]
    bound = binding(board, evidence, payload)
    reviews = evidence["reviews"]
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": GOAL,
        "lines": [bound["good"]],
        "provenance": {
            "source_fingerprint": source["source_marker"],
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": reviews[-1]["id"] if reviews else None,
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": evidence["mapper_version"],
            "fact_id": fact["id"],
            "detector_run_id": fact["detector_run_id"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "pin_prevention": bound,
            "pin_witness": payload["proof"],
            "source_outcome": payload["outcome"],
            "work_reservation": budget,
        },
    }
