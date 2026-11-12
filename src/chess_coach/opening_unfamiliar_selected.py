"""Reconstruct one exact, source-checked opening selection."""

from .learner_identity import normalize_identity
from .opening_unfamiliar import prepare
from .opening_unfamiliar_guard import check, start
from .opening_unfamiliar_options import available
from .opening_unfamiliar_selection import _board, _valid


def selected(db, root, learner, selection, *, measured=False, deadline=None):
    if not _valid(selection):
        raise ValueError("opening selection unavailable")
    subject = normalize_identity(learner)
    guard = start(db, root, subject)
    budget, subject, dataset, report, white, black = prepare(db, learner, deadline=deadline)
    color = selection["color"]
    board = _board(selection, report, white, black)
    found = available(db, root, subject, dataset, board, color, budget, selection["move"])
    if not found:
        raise ValueError("opening selection unavailable")
    measurement = None
    if measured:
        from .opening_unfamiliar_course_measure import current

        measurement = current(db, root, subject, color, board, found[0], budget)
    check(db, root, subject, guard, budget)
    result = {
        **report,
        "public_index_identity": list(guard[2]),
        "white": found[0] if color == "white" else None,
        "black": found[0] if color == "black" else None,
    }
    return (result, measurement) if measured else result
