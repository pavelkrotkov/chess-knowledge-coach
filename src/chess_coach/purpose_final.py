"""Evaluate exactly the played and nominated roots in one native search."""

import chess.engine

from .deep_execution_uci import analyse
from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .purpose_lines import native, roots, valid_pair, viewed, work
from .style_compare import candidates
from .style_history_lines import lines_safe


def final(engine, board, position, nominee):
    selected = [board.parse_uci(position["uci"]), board.parse_uci(nominee)]
    raw, error = analyse(
        engine, board, chess.engine.Limit(nodes=FINAL_NODES, time=FINAL_SECONDS), 2, selected
    )
    items, invalid = native(position, board, raw)
    result = {
        "lines": items,
        "work": work(raw, FINAL_NODES),
        "roots": [move.uci() for move in selected],
    }
    if error or invalid or not valid_pair(items) or set(roots(items)) != set(result["roots"]):
        return result, error or "invalid_candidate_search"
    return result, grade(board, position, items)


def grade(board, position, items):
    alternatives = viewed(items, board, position["uci"])
    compared = candidates(
        board, position["uci"], {"status": "complete", "result": {"alternatives": alternatives}}
    )
    if compared["status"] != "comparable":
        return compared["status"]
    lines = [item["line"] for item in alternatives]
    return None if lines_safe(board, lines) else "history_or_promotion_unsupported"
