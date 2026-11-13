"""Nominate an alternative without using the scout as comparison evidence."""

import chess.engine

from .deep_execution_uci import analyse
from .purpose_config import SCOUT_NODES, SCOUT_SECONDS
from .purpose_lines import native, roots, valid_pair, work


def scout(engine, board, position, candidates=None):
    limit = chess.engine.Limit(nodes=SCOUT_NODES, time=SCOUT_SECONDS)
    if candidates is None:
        raw, error = analyse(engine, board, limit, 2)
    else:
        raw, error = analyse(engine, board, limit, min(2, len(candidates)), candidates)
    items, invalid = native(position, board, raw)
    if candidates is not None:
        from .purpose_scout_center import choose

        return choose(candidates, raw, error, items, invalid)
    return ordinary(position, raw, error, items, invalid)


def ordinary(position, raw, error, items, invalid):
    moves = roots(items)
    result = {"lines": items, "work": work(raw, SCOUT_NODES)}
    if error or invalid or not valid_pair(items):
        return result, None, error or "invalid_scout"
    nominee = next((move for move in moves if move != position["uci"]), None)
    return result, nominee, None if nominee else "no_distinct_nominee"
