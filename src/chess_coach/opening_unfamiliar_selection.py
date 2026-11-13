"""Validate an exact selected opening and its current parent."""

from .opening_storage import position_key


def _valid(selection):
    return (
        isinstance(selection, dict)
        and set(selection) == {"color", "parent", "move"}
        and all(isinstance(value, str) and value for value in selection.values())
        and selection["color"] in ("white", "black")
    )


def _board(selection, report, white, black):
    if selection["color"] == "white":
        board, enabled = white, report["white_count"]
    else:
        board, enabled = black, report["parent"]
    if not enabled or selection["parent"] != position_key(board):
        raise ValueError("opening parent changed")
    return board
