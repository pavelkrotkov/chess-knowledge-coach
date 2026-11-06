"""Aggregate each named geometry at most once per selected public game."""

import json
from collections import Counter

from .named_structures import definitions
from .opening_profile_play import WINDOW_PLIES
from .opening_profile_window import shapes as window_shapes
from .opening_reference_url import site as valid_site


def summarize(db, selected):
    counts = Counter()
    examples = []
    missing = cutoffs = short = 0
    for game_id, first in selected:
        game = db.execute(
            "SELECT context,site,total_plies FROM games WHERE id=?", (game_id,)
        ).fetchone()
        rows = db.execute(
            "SELECT ply,shapes FROM moves WHERE game_id=? AND ply>=? AND ply<? ORDER BY ply LIMIT ?",
            (game_id, first, first + WINDOW_PLIES, WINDOW_PLIES),
        ).fetchall()
        shapes = window_shapes(rows, first, game[2])
        counts.update(shapes)
        missing += not bool(shapes)
        cutoffs += game[2] >= first + WINDOW_PLIES
        short += len(rows) < WINDOW_PLIES
        examples.append(
            {"context": json.loads(game[0]), "site": valid_site(game[1]), "first_ply": first}
        )
    names = definitions()
    families = [
        {"family": family, "color": color, "count": count, **names[family]}
        for (family, color), count in sorted(counts.items())
    ]
    return {
        "games": len(selected),
        "families": families,
        "no_supported_match": missing,
        "window_cutoffs": cutoffs,
        "short_windows": short,
        "examples": examples,
    }
