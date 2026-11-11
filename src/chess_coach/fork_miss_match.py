"""Require comparable dates, coverage, controls, and analysis."""

from .fork_miss_bounds import separated
from .fork_miss_time import _times
from .mate_game_trend import _comparable


def _resolved(sample):
    return all(
        (
            sample["eligible"] == sample["scanned"],
            not sample["timeouts"],
            not sample["pending"],
            not sample["unresolved"],
            sample["opportunities"] >= 5,
            sample["opportunity_games"] >= 3,
        )
    )


def _contexts_match(db, state, samples):
    first = _times(db, state["games"][:20])
    return first is not None and first == _times(db, state["games"][20:40]) and separated(samples)


def _qualified(state, samples, coverage, db):
    newer, earlier = samples
    dates = [game["date"] for game in state["games"]]
    if not state["selection_complete"] or not _comparable(
        samples, dates, coverage, state["unavailable"]
    ):
        return False
    if not all(_resolved(sample) for sample in samples):
        return False
    configs = newer["configs"] | earlier["configs"]
    if len(configs) != 1:
        return False
    return _contexts_match(db, state, samples)
