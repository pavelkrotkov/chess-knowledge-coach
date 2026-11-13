"""Compare two bounded, independent samples of completely replayed games."""

from .mate_game_collect import collect
from .mate_game_comparability import reason
from .recurrence_snapshot import read_snapshot
from .style_time_candidates import recent_games

CANDIDATE_LIMIT = 100


def _comparable(samples, dates, coverage, unavailable):
    return reason(samples, dates, coverage, unavailable) is None


def report(db, learner):
    with read_snapshot(db):
        games, coverage = recent_games(db, learner, limit=CANDIDATE_LIMIT)
        samples, dates, unavailable, duplicates = collect(db, learner, games)
        return {
            "newer": samples[0],
            "earlier": samples[1],
            "comparable": _comparable(samples, dates, coverage, unavailable),
            "coverage": coverage,
            "unavailable": unavailable,
            "duplicates": duplicates,
        }
