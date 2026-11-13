"""Build an optional existing-proof candidate filter for a capture cohort."""

from functools import partial

from .capture_finder_match import matches
from .capture_finder_prior import prepare


def accept_options(db, selection, expected):
    if expected is None:
        return {}
    return {"accept": partial(matches, db, selection, expected=expected)}


def prepared(db, subject, corpus, attempt, position, deadline, expired, harder):
    if not harder:
        position, expected = prepare(db, subject, corpus, attempt, position, deadline, expired)
        return position, expected, None
    if attempt is None or position is None:
        raise ValueError("harder capture unavailable")
    from .capture_difficulty import eligible

    difficulty = eligible(db, subject, corpus, position, attempt)
    return position, difficulty["expected"], difficulty


def finish(found, position, attempt, difficulty):
    if found is not None or not difficulty:
        return found
    return (
        position,
        {
            "items": [],
            "next_cursor": None,
            "matched": True,
            "harder": True,
            "harder_attempt": attempt,
            "difficulty_band": difficulty["band"],
            "status": "No compatible unfamiliar capture was found in the bounded search",
        },
    )
