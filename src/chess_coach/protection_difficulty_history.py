"""Select and compare two exact current protection assessments."""

import chess

from .fork_plan_history import _ambiguous
from .mate_assessment_rows import LIMIT, _end
from .protection_plan_history import _group
from .protection_progress_item import item


# The indexed newest window contains a boundary row for detecting tied cutoffs.
def _pair(db, subject, corpus, evidence, attempt, check):
    rows = _end(db, subject, "DESC")
    boundary = rows[LIMIT]["started_at"] if len(rows) > LIMIT else None
    exact, _ = _group(rows[:LIMIT], corpus, evidence, check)
    if len(exact) < 2:
        raise ValueError("harder protection unavailable")
    recent, earlier = (entry[0] for entry in exact[:2])
    after = [entry[0] for entry in exact[1:3]]
    if _ambiguous([recent, earlier], boundary) or _ambiguous(after, boundary):
        raise ValueError("harder protection ordering unavailable")
    if recent["attempt_id"] != attempt:
        raise ValueError("harder protection changed")
    return recent, earlier


# Replay both complete attempts and compare their original source contexts.
def _band(db, corpus, recent, earlier, check):
    latest = item(db, recent, corpus, check)
    previous = item(db, earlier, corpus, check)
    if latest["status"] != "correct" or previous["status"] != "correct":
        raise ValueError("harder protection unavailable")
    if latest["scope"][:-1] != previous["scope"][:-1]:
        raise ValueError("harder protection context changed")
    # The first result must precede the start of the second encounter.
    if previous["answered_at"] >= latest["started_at"]:
        raise ValueError("harder protection ordering unavailable")
    if chess.Board(recent["prompt_fen"]).epd() == chess.Board(earlier["prompt_fen"]).epd():
        raise ValueError("harder protection requires distinct positions")
    current = latest["scope"]
    if current[6] >= 19:
        raise ValueError("harder protection band unavailable")
    check()
    return (current[3], current[4], current[5], current[6] + 1), current[2]
