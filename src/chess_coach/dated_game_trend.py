"""Select a strictly revalidated historical cohort during a newer refresh."""

from .capture_game_trend_current import frontier_matches
from .capture_game_trend_validate import matches_frontier
from .mate_game_comparability import reason
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_validate import independent


def _newer(candidates, offset):
    first = candidates[offset][0]["projected_start"]
    return all(game["projected_start"] > first for game, _ in candidates[:offset])


def _sequence(state, candidates):
    ids = [game["id"] for game, _ in candidates]
    checked = [row[0] for row in state["checked"]]
    if not checked or checked[-1] != state["games"][-1]["id"]:
        return False
    if checked[0] not in ids:
        return False
    # A historical checked list must be an uninterrupted suffix of the
    # current bounded frontier. Only strictly newer arrivals may precede it.
    offset = ids.index(checked[0])
    if not offset or not matches_frontier(state, candidates[offset:]):
        return False
    return _newer(candidates, offset)


def _historical(state, candidates, coverage, signatures):
    if not state or not state["selection_complete"] or not independent(state):
        return False
    # The same metadata uncertainty and every checked source signature are
    # required, including rows excluded as duplicate or unavailable.
    if state.get("coverage") != coverage or signatures != state["checked"]:
        return False
    if not _sequence(state, candidates):
        return False
    # Both sample boundaries need distinct times and a separate 41st game.
    dates = [item["date"] for item in state["games"]]
    return reason([{"games": 20}, {"games": 20}], dates, coverage, state["unavailable"]) is None


def _current(state, candidates, frontier, signatures, strict):
    if strict:
        return frontier_matches(state, candidates, frontier, signatures)
    return frontier == state["frontier"] and signatures == state["checked"]


def _prior(db, learner, state, candidates, coverage, signatures):
    prior = state.get("prior") if not state["selection_complete"] else state
    if not prior:
        return None
    if prior is not state:
        candidates, coverage, _, signatures = snapshot(db, learner, prior["checked"])
    if _historical(prior, candidates, coverage, signatures):
        return prior, candidates, coverage, True
    return None


def choose(db, learner, state, *, strict=True):
    candidates, coverage, frontier, signatures = snapshot(db, learner, state["checked"])
    current = _current(state, candidates, frontier, signatures, strict)
    # Completed current work always replaces the historical view.
    if current and state["selection_complete"]:
        return state, candidates, coverage, False
    prior = _prior(db, learner, state, candidates, coverage, signatures)
    if prior:
        return prior
    if current:
        return state, candidates, coverage, False
    return None
