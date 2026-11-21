"""Narrow, source-bound misses of the named owned fork objective."""

from .fork_assessment_miss import reason
from .objective_contract import OWNED_HISTORY
from .objective_fork_contract import MISS_OBJECTIVE
from .objective_fork_miss_scope import supported
from .objective_short_history import history_hash

RULE = "owned-fork-objective-miss-v1"


def _reason(board, move, attacker, anchor):
    return reason(board, move, attacker, anchor) if supported(board, move) else None


def verdict(board, move, attacker, anchor, request, data, base):
    if (
        request["objective_version"] != MISS_OBJECTIVE
        or request["history_mode"] != OWNED_HISTORY
        or data.get("objective_version") != MISS_OBJECTIVE
        or data.get("history_mode") != OWNED_HISTORY
        or data.get("source_fingerprint") != request["source_hash"]
    ):
        return None
    why = _reason(board, move, attacker, anchor)
    if not why:
        return None
    return {
        **base,
        "status": "incorrect",
        "reason": why,
        "miss_rule": RULE,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
    }
