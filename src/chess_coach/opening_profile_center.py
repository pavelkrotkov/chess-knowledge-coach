"""Count four-ply center events at most once per selected public game."""

from collections import Counter

from .opening_profile_center_replay import inspect
from .opening_profile_center_window import PLIES


def summarize(db, selected, parent, move):
    counts = Counter()
    for game_id, first in selected:
        game = db.execute("SELECT total_plies FROM games WHERE id=?", (game_id,)).fetchone()
        if game is None:
            counts["unavailable"] += 1
            continue
        rows = db.execute(
            """SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply>=? AND ply<?
            ORDER BY ply LIMIT ?""",
            (game_id, first, first + PLIES, PLIES),
        ).fetchall()
        state, observed = inspect(rows, first, game[0], parent, move)
        counts[state] += 1
        if observed is not None:
            counts.update(key for key, present in observed.items() if present)
    return {
        key: counts[key]
        for key in (
            "valid",
            "short",
            "inconsistent",
            "unavailable",
            "capture",
            "recapture",
            "opened_d",
            "opened_e",
            "opened_any",
        )
    }
