"""Choose bounded recent source decisions without engine or outcome scores."""

import hashlib

from .style_schedule_coverage import summarize_coverage
from .style_schedule_scan import read_games
from .style_time_candidates import recent_games

MAX_GAMES = 10


def _rank(key, kind, game_id, position_id):
    value = f"{key}:{kind}:{game_id}:{position_id}"
    return hashlib.sha256(value.encode()).hexdigest()


def allocate(db, learner, key, sequence):
    games, coverage = recent_games(db, learner, limit=MAX_GAMES)
    candidates, skipped, duplicates, exhausted, reconstructed = read_games(db, games, sequence)
    targets = [item for item in candidates if item["in_check"]]
    targets.sort(key=lambda x: _rank(key, "target", x["game_id"], x["position_id"]))
    target = targets[sequence % len(targets)] if targets else None
    controls = [
        item for item in candidates if target is None or item["game_id"] != target["game_id"]
    ]
    controls.sort(key=lambda x: _rank(key, "control", x["game_id"], x["position_id"]))
    control = controls[sequence % len(controls)] if controls else None
    coverage = summarize_coverage(
        db, games, coverage, skipped, duplicates, exhausted, reconstructed
    )
    return coverage, (("target", target), ("control", control))
