"""Build an optional existing-proof candidate filter for a capture cohort."""

from functools import partial

from .capture_finder_match import matches


def accept_options(db, selection, expected):
    if expected is None:
        return {}
    return {"accept": partial(matches, db, selection, expected=expected)}
