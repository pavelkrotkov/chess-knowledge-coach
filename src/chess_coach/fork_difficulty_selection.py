"""Scope harder fork candidates before ranking and bind their references."""

from functools import partial

from .fact_fingerprint import canonical, digest
from .related_fork_match import candidate


def _score(raw, source, seen, baseline, *, side):
    if raw["type"] != "corpus":
        return None
    item = candidate(raw, source, seen, baseline)
    return item if item and item["fen"].split()[1] == side[0] else None


def options(difficulty):
    if difficulty is None:
        return {}
    start = difficulty["expected"]["rating_band"] * 200
    return {
        "rating_bounds": (start, start + 199),
        "score": partial(_score, side=difficulty["side"]),
    }


def scoped(selection, difficulty):
    if difficulty is None or selection is None:
        return selection
    scope = digest(canonical([selection[4], "fork-harder-v1", difficulty]))
    return (*selection[:4], scope, selection[5])


def signed_attempt(attempt, difficulty):
    if difficulty is None:
        return attempt
    return ["fork-harder-v1", difficulty["earlier"], attempt]


def selection_options(difficulty):
    return {"difficulty": difficulty} if difficulty else {}
