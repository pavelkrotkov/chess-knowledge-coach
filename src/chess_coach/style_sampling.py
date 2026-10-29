"""Describe the bounded attributable-game sample without inferring chronology."""


def coverage(limit, game_limited, scan_limited, skipped, duplicates):
    return {
        "requested_game_limit": limit,
        "effective_game_limit": limit,
        "selection_order": "descending local game ID, not game chronology",
        "sample_truncated": bool(game_limited or scan_limited),
        "omitted_attributable_games_lower_bound": int(bool(game_limited)),
        "omitted_attributable_games_unknown": bool(game_limited or scan_limited),
        "unprocessed_decisions_unknown": bool(
            game_limited or scan_limited or skipped or duplicates
        ),
    }
