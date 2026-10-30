"""Reconcile selection and deep results for one automatic worker game."""

from .deep_selection import select_deep
from .deep_selection_views import show_selection
from .pipeline_deep_counts import selection_counts
from .pipeline_deep_work import execute


def process_game(db, game_id, config, report, *, deadline=None):
    try:
        selected = select_deep(
            db,
            [game_id],
            learner=config.learner,
            per_game=config.deep_per_game,
            total=config.deep_per_game,
        )["games"][0]
    except Exception:
        report["detail"] = "selection_unavailable"
        return False
    if selected["status"] == "inputs_changed":
        report["detail"] = "selection_changed"
        return False
    if selected["status"] != "selected":
        return True
    report["selected_games"] += 1
    remaining = config.deep_max_jobs - report["processed"]
    try:
        result = execute(
            db, game_id, selected["selection_id"], config, remaining, deadline=deadline
        )
    except Exception:
        report["detail"] = "deep_unavailable"
        return False
    report["processed"] += len(result["processed"])
    counts = selection_counts(show_selection(db, game_id, config.learner))
    for key in ("selected", "capped_out", "pending", "insufficient", "unstable"):
        report[key] += counts[key]
    return _finished(result, report)


def _finished(result, report):
    if any(item["status"] == "stale" for item in result["processed"]):
        report["detail"] = "selection_changed"
        return False
    if result.get("detail"):
        report["detail"] = result["detail"]
        return False
    return True
