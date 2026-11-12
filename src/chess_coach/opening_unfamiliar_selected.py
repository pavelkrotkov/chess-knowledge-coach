"""Reconstruct one exact, source-checked opening selection."""

from .learner_identity import normalize_identity
from .opening_storage import position_key
from .opening_unfamiliar import prepare
from .opening_unfamiliar_guard import check, start
from .opening_unfamiliar_options import available


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


def selected(db, root, learner, selection):
    if not _valid(selection):
        raise ValueError("opening selection unavailable")
    subject = normalize_identity(learner)
    guard = start(db, root, subject)
    budget, subject, dataset, report, white, black = prepare(db, learner)
    color = selection["color"]
    board = _board(selection, report, white, black)
    found = available(db, root, subject, dataset, board, color, budget, selection["move"])
    if not found:
        raise ValueError("opening selection unavailable")
    check(db, root, subject, guard, budget)
    return {
        **report,
        "public_index_identity": list(guard[2]),
        "white": found[0] if color == "white" else None,
        "black": found[0] if color == "black" else None,
    }
