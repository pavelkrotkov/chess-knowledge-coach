"""Qualify one bounded public comparison against its all-root reference."""

from .opening_experiment import MAX_DISADVANTAGE
from .opening_queue_reference import public
from .style_history_lines import history_safe


def view(payload, board):
    result = payload["result"]
    if not history_safe(board):
        return {"status": "insufficient", "reason": "history_unavailable"}
    if result["status"] == "insufficient":
        return {"status": "insufficient", "reason": result.get("reason", "unavailable")}
    move = payload["selection"]["move"]
    if not public(result, move, board):
        return {"status": "insufficient", "reason": "reference_unverified"}
    lines = result["lines"]
    selected = next(item for item in lines if item["root_move"] == move)
    gap = lines[0]["score_value"] - selected["score_value"]
    return {
        "status": "admitted" if gap <= MAX_DISADVANTAGE else "materially_worse",
        "reference_gap_cp": gap,
        "depth": result["retained_depth"],
        "legal_roots": len(lines),
        "engine_sha256": payload["configuration"]["engine_sha256"],
        "requested_nodes": payload["configuration"]["requested_nodes"],
        "requested_seconds": payload["configuration"]["requested_seconds"],
        "source_index_sha256": payload["selection"]["reference_index_sha256"],
        "interpretation": "Public reference comparison; not an owned outcome or a soundness claim.",
    }
