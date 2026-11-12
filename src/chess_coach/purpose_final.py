"""Evaluate exactly the played and nominated roots in one native search."""

import chess.engine

from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .purpose_iteration_search import search
from .purpose_lines import viewed
from .style_compare import candidates
from .style_history_lines import lines_safe


def final(engine, board, position, nominee, deadline):
    selected = [board.parse_uci(position["uci"]), board.parse_uci(nominee)]
    state, error = search(
        engine,
        board,
        position,
        chess.engine.Limit(nodes=FINAL_NODES, time=FINAL_SECONDS),
        selected,
        deadline,
    )
    if state is None:
        return {"lines": [], "roots": [move.uci() for move in selected]}, error
    work = {
        "nodes": state.work["nodes"],
        "depth": state.work["depth"],
        "time_seconds": state.work["time"],
        "shared_search": True,
        "requested_nodes": FINAL_NODES,
        "node_limit_exceeded": state.work["nodes"] is not None
        and state.work["nodes"] > FINAL_NODES,
    }
    result = {
        "lines": state.best,
        "work": work,
        "roots": [move.uci() for move in selected],
        "retained_depth": state.depth,
    }
    if not state.best:
        return result, "no_complete_iteration"
    return result, grade(board, position, state.best)


def grade(board, position, items):
    alternatives = viewed(items, board, position["uci"])
    compared = candidates(
        board, position["uci"], {"status": "complete", "result": {"alternatives": alternatives}}
    )
    if compared["status"] != "comparable":
        return compared["status"]
    lines = [item["line"] for item in alternatives]
    return None if lines_safe(board, lines) else "history_or_promotion_unsupported"
