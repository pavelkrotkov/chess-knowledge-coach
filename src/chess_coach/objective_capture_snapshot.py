"""Bind an independently checked capture exemplar to its snapshot."""

import time

import chess

from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE, TARGET_VERSION
from .objective_capture_judge import judge
from .objective_contract import OWNED_HISTORY


def snapshot(board, view, review, evidence_id, version):
    objective = "capture_named_target" if version == TARGET_VERSION else "bounded_material_gain"
    target = view["objective"]["target"]
    square = chess.parse_square(target)
    witness = view["objective_witness"]["uci"][0]
    result = judge(
        board,
        board.parse_uci(witness),
        objective,
        square,
        3,
        time.monotonic,
        time.monotonic(),
        5.0,
        {},
    )
    if result["status"] != "correct":
        raise ValueError("capture exemplar unavailable")
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": objective,
        "lines": [witness],
        "provenance": {
            "source_fingerprint": view["source_fingerprint"],
            "evidence_id": evidence_id,
            "position_id": view["position_id"],
            "review_status": view["review_status"],
            "review_event_id": review["id"] if review else None,
            "lineage": view["lineage"],
            "objective_version": TARGET_OBJECTIVE if version == TARGET_VERSION else GAIN_OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "objective_target": target,
            "capture_objective": objective,
            "gain_threshold": 3,
        },
    }
