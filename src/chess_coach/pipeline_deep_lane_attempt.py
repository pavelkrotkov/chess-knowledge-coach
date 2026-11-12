"""Run one deep game with a bounded, durable retry."""

from .pipeline_deep_cursor import retire
from .pipeline_deep_game import process_game
from .pipeline_deep_game_finish import interrupted
from .pipeline_deep_lane_state import save
from .pipeline_deep_lane_validate import RETRIES


def attempt(db, config, report, state, lane, item, archive, seen, deadline):
    if item["attempts"] >= RETRIES:
        report["skipped_failures"] += 1
        report["status"] = "partial"
        return retire(db, state, lane, item, archive), True
    item = {**item, "attempts": item["attempts"] + 1}
    state = {**state, lane: item}
    save(db, config.learner, state)
    before = report["pending"]
    advanced = report["advanced"]
    ok = process_game(db, item["id"], config, report, deadline=deadline)
    pending = report["pending"] > before
    seen[item["id"]] = ok and not pending
    if not ok:
        report["status"] = "partial"
        if interrupted(report, deadline):
            report["capped"] = True
            if report["advanced"] > advanced:
                return {**state, lane: {**item, "attempts": 0}}, False
        if item["attempts"] >= RETRIES:
            report["skipped_failures"] += 1
            state = retire(db, state, lane, item, archive)
        return state, False
    if pending:
        return {**state, lane: {**item, "attempts": 0}}, False
    return retire(db, state, lane, item, archive), True
