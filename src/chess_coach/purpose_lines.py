"""Normalize native output without writing ordinary best-move roles."""

from .decision_line_view import view_line
from .deep_execution_lines import alternatives
from .deep_execution_work import shared_work


def native(position, board, raw):
    items, invalid = alternatives(position, board, raw)
    for item in items:
        item["line"]["role"] = "candidate"
    return items, invalid


def roots(items):
    return [item["line"]["root_move"] for item in items]


def viewed(items, board, played):
    return [
        {"rank": item["rank"], "line": view_line(item["line"], board, played)} for item in items
    ]


def work(raw, requested_nodes):
    result = shared_work(raw)
    result["requested_nodes"] = requested_nodes
    result["node_limit_exceeded"] = (
        result["nodes"] is not None and result["nodes"] > requested_nodes
    )
    return result


def valid_pair(items):
    moves = roots(items)
    return len(moves) == 2 and None not in moves and len(set(moves)) == 2
