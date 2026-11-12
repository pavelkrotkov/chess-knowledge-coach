"""Validate native ranked lines before retaining an iteration."""

from .deep_execution_lines import line
from .style_metrics import HORIZON

MAX_PV_PLIES = 128
DEFAULT_BOUNDS = (HORIZON, MAX_PV_PLIES, HORIZON)


def checked(position, board, info, bounds):
    moves = info.get("pv")
    if not isinstance(moves, list) or not bounds[0] <= len(moves) <= bounds[1]:
        return None
    item, invalid = line(position, board, "best", info)
    if invalid or item is None or not _structural(item):
        return None
    item["role"] = "candidate"
    return {"line": item}


def paired(first, second, roots):
    if first is None or second is None:
        return None
    same_depth = first["line"]["depth"] == second["line"]["depth"]
    moves = {first["line"]["root_move"], second["line"]["root_move"]}
    return (first, second) if same_depth and moves == roots else None


def _structural(item):
    return (
        item["root_move"] is not None
        and item["score_kind"] in {"cp", "mate"}
        and item["score_bound"] == "exact"
        and type(item["score_value"]) is int
        and type(item["depth"]) is int
        and item["depth"] > 0
    )
