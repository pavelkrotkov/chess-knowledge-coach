"""Nominate repeated learner pre-move positions from bounded metadata."""

import time
from collections import defaultdict

from .opening_explore_boundary import boundary
from .opening_explore_positions import game_positions as _game
from .tactical_course_budget import PreviewUnavailable

MAX_PLIES = 40


def candidates(db, rows, budget):
    groups = defaultdict(list)
    scanned = 0
    incomplete = False
    for game, color in rows:
        try:
            with budget.scope(snapshot=False):
                last_ply = min(MAX_PLIES, boundary(db, game["id"]))
                positions = db.connection.execute(
                    """SELECT id,ply,
                    CASE WHEN length(substr(CAST(fen AS BLOB),1,201))<=200 THEN fen END AS fen
                    FROM positions WHERE game_id=? AND ply<=? ORDER BY ply LIMIT ?""",
                    (game["id"], last_ply, MAX_PLIES),
                ).fetchall()
                items = _game(game, color, positions)
                if any(position["fen"] is None for position in positions):
                    incomplete = True
        except PreviewUnavailable:
            incomplete = True
            if time.monotonic() >= budget.expires:
                break
            continue
        scanned += 1
        for key, item in items:
            groups[key].append(item)
    return groups, scanned, incomplete


def ranked(groups):
    repeated = [(key, items) for key, items in groups.items() if len(items) >= 2]
    return sorted(repeated, key=lambda pair: (-len(pair[1]), pair[0]))
