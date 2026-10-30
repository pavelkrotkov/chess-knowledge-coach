"""Explain bounded sample coverage without implying analysis currentness."""

from .style_schedule_clock import reached


def summarize_coverage(db, games, coverage, skipped, duplicates, exhausted, reconstructed):
    coverage.update(
        {
            "examined_games": len(games),
            "reconstructed_games": reconstructed,
            "unreconstructed_games": len(games) - reconstructed,
            "without_completed_analysis_checkpoint": _without_analysis(db, games),
            "analysis_checkpoint_currentness_unchecked": True,
            "omitted_attributable_lower_bound": int(coverage["game_limit_reached"]),
            "skipped_games": skipped,
            "duplicate_games": duplicates,
            "history_budget_exhausted": exhausted and not reached(),
            "deadline_reached": reached(),
            "selection_note": "Deterministic recent-game target and hash control; not a random or representative sample.",
        }
    )
    return coverage


def _without_analysis(db, games):
    return sum(
        db.connection.execute(
            "SELECT 1 FROM pipeline_stages WHERE game_id=? AND stage='analysis' AND status='complete'",
            (game["id"],),
        ).fetchone()
        is None
        for game, _color in games
    )
