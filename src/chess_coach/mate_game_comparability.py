"""Explain the shared independent game-cohort comparability gate."""

from .mate_game_collect import SAMPLE_SIZE
from .style_time_uncertainty import has_unknown


def _boundary(dates, coverage):
    if dates[SAMPLE_SIZE - 1] == dates[SAMPLE_SIZE]:
        return "between_tie"
    if len(dates) > 2 * SAMPLE_SIZE:
        return "frontier_tie" if dates[2 * SAMPLE_SIZE - 1] == dates[2 * SAMPLE_SIZE] else None
    return "frontier_limit" if coverage["game_limit_reached"] else None


def reason(samples, dates, coverage, unavailable):
    if has_unknown(coverage) or unavailable:
        return "source_unavailable"
    if any(sample["games"] != SAMPLE_SIZE for sample in samples):
        return "too_few_games"
    return _boundary(dates, coverage)
