"""Account for one deep-lane candidate and avoid cross-lane duplicate work."""

from .pipeline_deep_cursor import retire
from .pipeline_deep_lane_attempt import attempt
from .pipeline_deep_recent_owner import owned


def step(db, config, report, state, lane, item, archive, seen, deadline):
    report["examined"] += 1
    report["lanes"][lane] += 1
    if item["id"] in seen:
        if state[lane] is not None and not seen[item["id"]]:
            return state, False
        return retire(db, state, lane, item, archive), True
    if lane == "recent" and not owned(db, config, item):
        report["recent_unavailable"] += 1
        return retire(db, state, lane, item, archive), True
    return attempt(db, config, report, state, lane, item, archive, seen, deadline)
