"""Choose bounded recent source decisions without engine or outcome scores."""

from .style_schedule_coverage import summarize_coverage
from .style_schedule_rotation import choose
from .style_schedule_scan import read_games
from .style_time_candidates import recent_games

MAX_GAMES = 10


def allocate(db, learner, key, sequence):
    games, coverage = recent_games(db, learner, limit=MAX_GAMES)
    candidates, skipped, duplicates, exhausted, reconstructed = read_games(db, games, sequence)
    targets = [item for item in candidates if item["in_check"]]
    target = choose(db, key, "target", targets)
    controls = [
        item for item in candidates if target is None or item["game_id"] != target["game_id"]
    ]
    control = choose(db, key, "control", controls)
    coverage = summarize_coverage(
        db, games, coverage, skipped, duplicates, exhausted, reconstructed
    )
    return coverage, (("target", target), ("control", control)), candidates
