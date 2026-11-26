"""Bind an independently checked capture exemplar to its snapshot."""

import time

import chess

from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE, TARGET_VERSION
from .objective_capture_judge import judge
from .objective_contract import OWNED_HISTORY


def snapshot(board, view, review, evidence_id, version, *, check=None):
    return qualify(board, view, review, evidence_id, version, check=check)[0]


def qualify(board, view, review, evidence_id, version, *, check=None):
    """Return the ordinary snapshot and the actual successful verifier result."""
    objective = "capture_named_target" if version == TARGET_VERSION else "bounded_material_gain"
    target = view["objective"]["target"]
    square = chess.parse_square(target)
    witness = view["objective_witness"]["uci"][0]
    clock = _clock(check)
    options = {"check": check} if check is not None else {}
    result = judge(
        board,
        board.parse_uci(witness),
        objective,
        square,
        3,
        clock,
        clock(),
        5.0,
        {},
        **options,
    )
    if result["status"] != "correct":
        raise ValueError("capture exemplar unavailable")
    return _snapshot(board, view, review, evidence_id, version), result


def _snapshot(board, view, review, evidence_id, version):
    objective = "capture_named_target" if version == TARGET_VERSION else "bounded_material_gain"
    target = view["objective"]["target"]
    witness = view["objective_witness"]["uci"][0]
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


def _clock(check):
    if check is None:
        return time.monotonic

    def read():
        check()
        return time.monotonic()

    return read
