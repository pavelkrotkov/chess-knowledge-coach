"""Bounded attributable decisions, outcomes and familiarity history."""

from .repertoire_sources import MAX_GAMES, games_for_learner
from .style_familiarity import familiarity
from .style_game_sources import collect_games
from .style_sampling import coverage as sample_coverage


def source_games(db, learner, *, max_games=MAX_GAMES):
    games, limited, scan_limited = games_for_learner(db, learner, limit=max_games)
    rows, contexts, outcomes, skipped, duplicates = collect_games(db, games, learner)
    undated = sum(not item["observation_at"] for item in contexts)
    incomplete = bool(limited or scan_limited or skipped or duplicates or undated)
    familiarity(contexts, incomplete)
    return {
        "games": rows,
        **sample_coverage(max_games, limited, scan_limited, skipped, duplicates),
        "examined_games": len(games),
        "independent_games": len(rows),
        "duplicate_games": duplicates,
        "skipped_games": skipped,
        "game_limit_reached": limited,
        "scan_limit_reached": scan_limited,
        "undated_decisions": undated,
        "familiarity_history_incomplete": incomplete,
        "decisions": len(contexts),
        "outcomes": outcomes,
    }
