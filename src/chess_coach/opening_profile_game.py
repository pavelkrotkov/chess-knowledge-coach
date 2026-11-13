"""Read and validate the two ordered windows of one indexed game."""

import json

from .opening_profile_play import STORED_PLIES, WINDOW_PLIES
from .opening_profile_window import shapes
from .opening_reference_url import site as valid_site

EXTENDED_PLIES = 36


def project(db, game_id, first):
    game = db.execute(
        "SELECT context,site,total_plies FROM games WHERE id=?", (game_id,)
    ).fetchone()
    if game is None:
        raise ValueError("ordered profile game unavailable")
    rows = db.execute(
        "SELECT ply,shapes FROM moves WHERE game_id=? AND ply>=? AND ply<? ORDER BY ply LIMIT ?",
        (game_id, first, first + EXTENDED_PLIES, EXTENDED_PLIES),
    ).fetchall()
    early_rows = rows[:WINDOW_PLIES]
    early = shapes(early_rows, first, game[2])
    extended = shapes(rows, first, game[2], limit=EXTENDED_PLIES)
    return {
        "early": early,
        "extended": extended,
        "early_span": len(early_rows),
        "span": len(rows),
        "cutoff": len(rows) == EXTENDED_PLIES and game[2] >= first + EXTENDED_PLIES,
        "frontier": len(rows) < EXTENDED_PLIES and game[2] > STORED_PLIES,
        "ended": len(rows) < EXTENDED_PLIES and game[2] <= STORED_PLIES,
        "example": {
            "context": json.loads(game[0]),
            "site": valid_site(game[1]),
            "first_ply": first,
            "extended_positions": len(rows),
            "later_only": sorted(extended - early),
        },
    }
