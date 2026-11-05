"""Summarize game outcomes in one independent sample."""

from .mate_game_sample import game_outcomes


def empty():
    """Start a cohort without assuming any opportunities exist."""
    return {
        "games": 0,
        "opportunities": 0,
        "misses": 0,
        "miss_games": 0,
        "newest": None,
        "oldest": None,
        "examples": [],
    }


def add(sample, started, pairs):
    """Count positions separately from games and cap source links."""
    opportunities, misses, examples = game_outcomes(pairs)
    sample["games"] += 1
    sample["opportunities"] += opportunities
    sample["misses"] += misses
    sample["miss_games"] += bool(misses)
    sample["newest"] = sample["newest"] or started
    sample["oldest"] = started
    sample["examples"].extend(examples[: max(0, 10 - len(sample["examples"]))])
