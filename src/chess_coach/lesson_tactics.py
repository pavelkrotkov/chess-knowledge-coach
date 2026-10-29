"""Material and fork lesson facts from checked sources."""

from .lesson_adapter_common import line as checked_line
from .lesson_adapter_common import valid_square
from .lesson_lines import legal_san


def _fork(evidence, fen):
    note = evidence.get("fork_explanation") or {}
    move, targets = note.get("move"), note.get("targets") or []
    if not legal_san(fen, [move]) or not targets or not all(map(valid_square, targets)):
        return [], []
    facts = [f"The tested move {move} attacks targets on {', '.join(targets)}."]
    sample = note.get("sample") or {}
    line = checked_line(
        fen,
        "One tested defense and capture",
        [move, sample.get("reply_san"), sample.get("capture_san")],
    )
    return facts, [line]


def _defense_line(note, fen):
    anchor, fork = note.get("anchor") or {}, note.get("fork") or {}
    if anchor:
        first, label, origin = (
            anchor.get("san"),
            "Tested alternative and fork",
            "The tested alternative",
        )
    else:
        first = next(iter(note.get("played") or []), None)
        label, origin = "Recorded played-search fork", "The recorded engine continuation"
    return checked_line(fen, label, [first, fork.get("san")]), fork.get("targets") or [], origin


def _defense(evidence, fen):
    note = evidence.get("fork_defense_explanation") or {}
    line, targets, origin = _defense_line(note, fen)
    if not line or not targets or not all(map(valid_square, targets)):
        return [], []
    return [f"{origin} includes a fork against {', '.join(targets)}."], [line]
