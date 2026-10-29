"""Validate stored line provenance before presenting native engine results."""

import json

from .analysis_comparison import SEMANTICS
from .decision_line_replay import replay_line


def view_line(row, board, played):
    result = dict(row)
    wdl_json = result.pop("wdl_json")
    result["wdl"] = None
    result.update({"san": [], "terminal": None, "terminal_reason": None, "status": "unavailable"})
    if not _compatible(row, board):
        return _rejected(result, board, played)
    try:
        result.update(replay_line(board, row["pv"], row["role"], played))
        result["wdl"] = json.loads(wdl_json) if wdl_json else None
    except (ValueError, TypeError):
        return _rejected(result, board, played)
    if not result["san"] or row["score_kind"] is None or row["score_value"] is None:
        return _rejected(result, board, played)
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


def _rejected(result, board, played):
    # A missing PV can still identify the root that was actually requested.
    if not _requested_played_root(result, board, played):
        result["root_move"] = None
    for field in (
        "score_kind",
        "score_value",
        "score_bound",
        "wdl",
        "pv",
        "nodes",
        "depth",
        "seldepth",
        "time_seconds",
        "terminal",
        "terminal_reason",
    ):
        result[field] = None
    result["san"] = []
    return result


def _requested_played_root(row, board, played):
    pov = "white" if board.turn else "black"
    return (
        not row["pv"]
        and row["role"] == "played"
        and row["root_move"] == played
        and row["decision_fen"] == board.fen()
        and row["score_pov"] == pov
        and row["semantics"] == SEMANTICS
    )
