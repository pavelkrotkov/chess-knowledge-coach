"""Check the recorded bounded fork witness against the first move."""

import json

import chess

from .capture_plan_result import _move
from .fork_proof import MAX_REPLIES
from .objective_events import assistance
from .objective_provenance import SECONDS


def _limits(proof, limits):
    seconds, replies = limits.get("compute_timeout_seconds"), proof.get("legal_replies")
    return (
        type(replies) is int
        and 0 < replies <= MAX_REPLIES
        and isinstance(proof.get("branches"), list)
        and len(proof["branches"]) == replies
        and limits.get("reply_limit") == MAX_REPLIES
        and type(seconds) in {int, float}
        and 0 < seconds <= SECONDS
    )


def _named(proof, data, board, move):
    return (
        data["fork_attacker"] == chess.square_name(move.from_square)
        and proof.get("attacker") == chess.square_name(move.to_square)
        and isinstance(proof.get("targets"), list)
        and data["fork_anchor"] in proof["targets"]
        and proof.get("move") == move.uci()
        and proof.get("san") == board.san(move)
        and proof.get("minimum_gain") == 3
    )


def correct(result, events, board, move, row):
    data = json.loads(row["provenance_json"])
    proof, limits = result.get("proof"), result.get("limits")
    if not isinstance(proof, dict) or not isinstance(limits, dict):
        return False
    return all(
        (
            result.get("status") == "correct",
            result.get("reason") == "named_fork_and_gain_proved",
            result.get("assistance") == assistance(events[:-1]),
            result.get("proven_gain_floor") == 3,
            _move(result, board, move),
            _named(proof, data, board, move),
            _limits(proof, limits),
        )
    )
