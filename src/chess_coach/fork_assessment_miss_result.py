"""Create and replay the versioned certified fork miss verdict."""

import json

import chess

from .fork_assessment_miss import VERSION, reason
from .objective_short_history import history_hash
from .related_capture_assessment import HISTORY
from .related_fork_assessment_scope import is_source


def verdict(board, move, attacker, anchor, request, data, base):
    if request["history_mode"] != HISTORY or not data.get("related_fork", {}).get("assessment"):
        return None
    why = reason(board, move, attacker, anchor)
    if not why:
        return None
    return {
        **base,
        "status": "incorrect",
        "reason": why,
        "miss_rule": VERSION,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
    }


def valid(result, board, move, session):
    if (
        session is None
        or not is_source(session)
        or result.get("status") != "incorrect"
        or result.get("miss_rule") != VERSION
    ):
        return False
    data = json.loads(session["provenance_json"])
    attacker = chess.parse_square(data["fork_attacker"])
    anchor = chess.parse_square(data["fork_anchor"])
    expected = reason(board, move, attacker, anchor)
    return expected is not None and result.get("reason") == expected
