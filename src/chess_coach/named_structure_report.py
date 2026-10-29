"""Read-only named structure history over versioned atomic episode sources."""

from .named_structure_intervals import game_history
from .named_structure_source import MAX_GAMES, attributable_games
from .named_structures import VERSION, VERSIONS, definitions


def structure_report(db, learner, *, version=VERSION):
    """Summarize up to 100 attributable games with current atomic episodes."""
    families = definitions(version)
    games, scan_limit = attributable_games(db, learner)
    items, unknown, truncated_games = [], 0, 0
    for game_id, color in games[:MAX_GAMES]:
        found, unmatched, truncated = game_history(db, game_id, color, version)
        items.extend(found)
        unknown += unmatched
        truncated_games += truncated
    summaries = []
    for key, definition in families.items():
        selected = [item for item in items if item["family"] == key]
        summaries.append(
            {
                "family": key,
                **definition,
                "episodes": len(selected),
                "games": len({item["game_id"] for item in selected}),
                "items": selected,
            }
        )
    return {
        "version": version,
        "versions": list(VERSIONS),
        "games_examined": min(len(games), MAX_GAMES),
        "game_limit_reached": len(games) > MAX_GAMES,
        "scan_limit_reached": scan_limit,
        "position_limit_games": truncated_games,
        "unmatched_positions": unknown,
        "families": summaries,
    }
