"""Compare two bounded, independent samples of completely replayed games."""

from .mate_game_collect import SAMPLE_SIZE, collect
from .recurrence_snapshot import read_snapshot
from .style_time_candidates import recent_games
from .style_time_uncertainty import has_unknown

CANDIDATE_LIMIT = 100


def _comparable(samples, dates, coverage, unavailable):
    if has_unknown(coverage) or unavailable:
        return False
    if any(sample["games"] != SAMPLE_SIZE for sample in samples):
        return False
    if dates[SAMPLE_SIZE - 1] == dates[SAMPLE_SIZE]:
        return False
    if len(dates) > 2 * SAMPLE_SIZE:
        return dates[2 * SAMPLE_SIZE - 1] != dates[2 * SAMPLE_SIZE]
    return not coverage["game_limit_reached"]


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
