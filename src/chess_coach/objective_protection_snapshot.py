"""Bind a proved exemplar to the originally threatened piece."""

import time

import chess

from .objective_contract import OWNED_HISTORY
from .objective_protection_before import probe
from .objective_protection_contract import OBJECTIVE
from .objective_protection_judge import judge


def snapshot(board, view, review, evidence_id):
    before = probe(board)
    if before is None:
        raise ValueError("protection threat unavailable")
    target = next(iter(before["targets"]))
    _check_recorded_target(board, view, target)
    move = view["objective_witness"]["uci"][0]
    result = judge(board, board.parse_uci(move), target, time.monotonic, time.monotonic(), 5.0, {})
    if result["status"] != "correct":
        raise ValueError("protection exemplar unavailable")
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "protect_threatened_piece",
        "lines": [move],
        "provenance": {
            "source_fingerprint": view["source_fingerprint"],
            "evidence_id": evidence_id,
            "position_id": view["position_id"],
            "review_status": view["review_status"],
            "review_event_id": review["id"] if review else None,
            "lineage": view["lineage"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "objective_target": chess.square_name(target),
            "gain_threshold": 3,
        },
    }


def _check_recorded_target(board, view, original):
    try:
        played = board.parse_uci(view["witness_lines"]["played"]["uci"][0])
        recorded = chess.parse_square(view["objective"]["target"])
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("protection target unavailable") from None
    expected = played.to_square if played.from_square == original else original
    if recorded != expected:
        raise ValueError("protection target changed")
