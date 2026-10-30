"""Describe the bounded attributable-game sample without inferring chronology."""


def coverage(limit, game_limited, unknown_projection, unknown_time, skipped, duplicates):
    return {
        "requested_game_limit": limit,
        "effective_game_limit": limit,
        "selection_order": "descending validated UTC game-start time; local ID breaks exact ties nonchronologically",
        "sample_truncated": bool(game_limited or unknown_projection),
        "omitted_attributable_games_lower_bound": int(bool(game_limited)) + unknown_time,
        "omitted_attributable_games_unknown": bool(game_limited or unknown_projection),
        "unprocessed_decisions_unknown": bool(
            game_limited or unknown_projection or skipped or duplicates
        ),
    }
