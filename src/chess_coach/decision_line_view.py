"""Validate stored line provenance before presenting native engine results."""

import json

from .analysis_comparison import SEMANTICS
from .decision_line_replay import replay_line


def view_line(row, board, played):
    result = dict(row)
    result["wdl"] = json.loads(result.pop("wdl_json")) if row["wdl_json"] else None
    result.update({"san": [], "terminal": None, "terminal_reason": None, "status": "unavailable"})
    if not _compatible(row, board):
        return result
    try:
        result.update(replay_line(board, row["pv"], row["role"], played))
    except (ValueError, TypeError):
        return result
    if result["san"] and row["score_kind"] is not None and row["score_value"] is not None:
        result["status"] = "limited"
    return result


def _compatible(row, board):
    moves = (row["pv"] or "").split()
    root = moves[0] if moves else None
    pov = "white" if board.turn else "black"
    return (
        row["semantics"] == SEMANTICS
        and row["root_move"] == root
        and row["decision_fen"] == board.fen()
        and row["score_pov"] == pov
    )
