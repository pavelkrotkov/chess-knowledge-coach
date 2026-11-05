"""Run one selected recent game within the ordinary budget."""

from .pipeline_game import process_game
from .pipeline_recent import WINDOW, select
from .pipeline_recent_turn import advance, claim


def empty_recent():
    return {
        "examined": 0,
        "selected": 0,
        "current": 0,
        "failed": 0,
        "over_budget": 0,
        "invalid": 0,
        "analysis_complete": 0,
        "analysis_failed": 0,
    }


def _recent(db, config, engine_hash, *, single):
    limit = min(WINDOW, config.max_scan if single else config.max_scan - 1)
    if single:
        claim(db, config.learner, next_recent=False)
    item, stats, state = select(db, config, engine_hash, limit)
    stats["analysis_complete"] = 0
    stats["analysis_failed"] = 0
    return item, stats, state


def run_recent(db, config, engine_hash, *, single):
    item, stats, state = _recent(db, config, engine_hash, single=single)
    if item is None:
        advance(db, config.learner, state)
        return item, stats, None
    result = process_game(db, *item, config, engine_hash)
    stages = result["stages"]
    if stages and stages[0]["status"] == "complete":
        stats["analysis_complete"] = 1
    else:
        stats["analysis_failed"] = 1
    advance(db, config.learner, state)
    return item, stats, result
