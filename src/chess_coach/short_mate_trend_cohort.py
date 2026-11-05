"""Bounded indexed frontier and provenance checks for game cohorts."""

import time

from .fact_fingerprint import canonical, digest
from .mate_game_trend import CANDIDATE_LIMIT
from .recurrence_snapshot import read_snapshot
from .short_mate_game_source import _signature
from .style_time_candidates import recent_games


def fingerprint(value):
    return digest(canonical(value))


def snapshot(db, learner, checked=(), *, seconds=1.0):
    deadline = time.monotonic() + seconds
    with read_snapshot(db):
        games, coverage = recent_games(db, learner, limit=CANDIDATE_LIMIT)
        frontier = fingerprint(
            [[game["id"], game["projected_start"]] for game, _ in games] + [coverage]
        )
        lookup = {game["id"]: game for game, _ in games}
        signatures = []
        for game_id, _ in checked:
            if time.monotonic() >= deadline:
                raise ValueError("frontier unavailable")
            signature = fingerprint(_signature(db, lookup[game_id])) if game_id in lookup else None
            signatures.append([game_id, signature])
        return games, coverage, frontier, signatures
