"""Recheck the versioned owned-fork miss reason on the original board."""

import json

import chess

from .objective_contract import OWNED_HISTORY
from .objective_fork_contract import MISS_OBJECTIVE, is_miss_source
from .objective_fork_owned_miss import RULE, _reason


def valid(result, board, move, session):
    if (
        session is None
        or not is_miss_source(session)
        or result.get("status") != "incorrect"
        or result.get("miss_rule") != RULE
    ):
        return False
    data = json.loads(session["provenance_json"])
    if data.get("objective_version") != MISS_OBJECTIVE or data.get("history_mode") != OWNED_HISTORY:
        return False
    attacker = chess.parse_square(data["fork_attacker"])
    anchor = chess.parse_square(data["fork_anchor"])
    expected = _reason(board, move, attacker, anchor)
    return expected is not None and result.get("reason") == expected
