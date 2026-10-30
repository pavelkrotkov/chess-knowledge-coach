"""Nominate an alternative without using the scout as comparison evidence."""

import chess.engine

from .deep_execution_uci import analyse
from .purpose_config import SCOUT_NODES, SCOUT_SECONDS
from .purpose_lines import native, roots, valid_pair, work


def scout(engine, board, position):
    raw, error = analyse(
        engine, board, chess.engine.Limit(nodes=SCOUT_NODES, time=SCOUT_SECONDS), 2
    )
    items, invalid = native(position, board, raw)
    moves = roots(items)
    result = {"lines": items, "work": work(raw, SCOUT_NODES)}
    if error or invalid or not valid_pair(items):
        return result, None, error or "invalid_scout"
    nominee = next((move for move in moves if move != position["uci"]), None)
    return result, nominee, None if nominee else "no_distinct_nominee"
