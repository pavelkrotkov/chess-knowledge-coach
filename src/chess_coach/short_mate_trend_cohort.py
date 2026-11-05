"""Bounded indexed frontier and provenance checks for game cohorts."""

import time

from .fact_fingerprint import canonical, digest
from .mate_game_trend import CANDIDATE_LIMIT
from .objective_source_budget import MAX_GAME_BYTES
from .recurrence_snapshot import read_snapshot
from .short_mate_game_source import _signature
from .style_time_candidates import recent_games


def fingerprint(value):
    return digest(canonical(value))


def signature(db, game):
    # Oversized sources are never evidence. The marker changes when they fit
    # the replay bounds, so repairing a formerly unavailable game invalidates cache.
    game_id = game["id"]
    size = db.connection.execute(
        "SELECT length(CAST(pgn AS BLOB)) FROM games WHERE id=?", (game_id,)
    ).fetchone()[0]
    if size > MAX_GAME_BYTES:
        return "oversized"
    extra = db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET 1000", (game_id,)
    ).fetchone()
    return "oversized" if extra else fingerprint(_signature(db, game))


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
            value = signature(db, lookup[game_id]) if game_id in lookup else None
            signatures.append([game_id, value])
        return games, coverage, frontier, signatures
