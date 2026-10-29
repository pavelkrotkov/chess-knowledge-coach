"""Look up current learner selection without requiring it to exist."""

from .deep_selection_views import show_selection


def selection(db, game_id, learner):
    try:
        return show_selection(db, game_id, learner)
    except ValueError:
        return None


def selection_coverage(selected):
    coverage = selected["coverage"]
    return {
        "selection_eligible": coverage["eligible"],
        "selection_capped_out": coverage["capped_out"],
        "selection_omitted_critical": coverage["omitted_critical"],
        "selection_missing_scores": coverage["missing_scores"],
    }
