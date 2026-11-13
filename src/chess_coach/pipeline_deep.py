"""Run independently bounded selection and deep work after the cheap pipeline."""

from .pipeline_deep_config import public_limits
from .pipeline_deep_lane import work
from .pipeline_deep_lane_state import claim
from .pipeline_deep_limits import at_capacity, finish


def process_deep(db, config, *, deadline=None):
    report = {
        "status": "disabled",
        "examined": 0,
        "selected_games": 0,
        "processed": 0,
        "advanced": 0,
        "selected": 0,
        "pending": 0,
        "capped_out": 0,
        "insufficient": 0,
        "unstable": 0,
        "limits": public_limits(config),
        "capped": False,
        "lanes": {"recent": 0, "archive": 0},
        "recent_unavailable": 0,
        "unavailable": 0,
        "skipped_failures": 0,
    }
    if not config.deep_enabled:
        return report
    report["status"] = "complete"
    lane, state = claim(db, config.learner, config.deep_per_game)
    seen = {}
    state, more = work(db, config, report, state, lane, seen, deadline)
    if (
        not report["capped"]
        and report["pending"] == 0
        and report["examined"] < config.deep_max_scan
        and not at_capacity(report, config)
    ):
        other = "archive" if lane == "recent" else "recent"
        state, other_more = work(db, config, report, state, other, seen, deadline)
        more = more or other_more
    return finish(report, config, more)
