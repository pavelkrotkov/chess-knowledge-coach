"""Build an optional existing-proof candidate filter for a capture cohort."""

from functools import partial

from .capture_finder_match import prepared_matches
from .capture_finder_prepared import prepared as prepared_proof
from .capture_finder_prior import prepare


def operations(db, selection, expected, subject, games, version, difficulty):
    run = partial(prepared_proof, subject=subject, games=games, version=version)
    match = partial(prepared_matches, subject=subject, games=games)
    accept = (
        {} if expected is None else {"accept": partial(match, db, selection, expected=expected)}
    )
    return run, accept


def prepared(db, subject, corpus, attempt, position, deadline, expired, harder):
    if not harder:
        position, expected = prepare(db, subject, corpus, attempt, position, deadline, expired)
        return position, expected, None
    if attempt is None or position is None:
        raise ValueError("harder capture unavailable")
    from .capture_difficulty import checked

    def check():
        if expired(deadline):
            raise ValueError("capture finder deadline")

    difficulty = checked(db, subject, corpus, position, attempt, check)
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


def decorate(result, expected, difficulty):
    result["items"][0]["assessment_available"] = True
    result["items"][0]["assessment_proved"] = True
    result["certified"] = True
    result["matched"] = expected is not None
    if difficulty:
        result.update(
            harder=True, harder_attempt=difficulty["attempt"], difficulty_band=difficulty["band"]
        )
    return result
