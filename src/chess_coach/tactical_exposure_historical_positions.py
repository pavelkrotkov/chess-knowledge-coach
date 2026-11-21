"""Extract potentially delivered positions from a verified historical export."""

from .fact_fingerprint import digest
from .tactical_exposure_pgn import positions as pgn_positions
from .tactical_exposure_positions import MAX_CHAPTERS, MAX_TOTAL_POSITIONS


def _chapters(course, state):
    chapters = course.get("chapters")
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= MAX_CHAPTERS:
        return None
    states = state.get("chapters")
    if not isinstance(states, list) or len(states) != len(chapters):
        return None
    if any(value not in {"new", "pending", "done"} for value in states):
        return None
    return chapters, states


def positions(course, state):
    selected = _chapters(course, state)
    if selected is None:
        return None
    chapters, states = selected
    result = set()
    for chapter, status in zip(chapters, states, strict=True):
        if status in {"pending", "done"}:
            result.update(digest(key) for key in pgn_positions(chapter["pgn"]))
            if len(result) > MAX_TOTAL_POSITIONS:
                raise ValueError("tactical material exceeds exposure limit")
    return result
