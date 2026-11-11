"""Filter an unfamiliar fork candidate by the prior frozen cohort."""

from functools import partial

from .fork_comparison_context import context


def matches(db, expected, candidate):
    if candidate["type"] != "corpus":
        return False
    try:
        return context(db, candidate["version"], candidate["key"]) == expected
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def accept_options(db, expected):
    return {} if expected is None else {"accept": partial(matches, db, expected)}
