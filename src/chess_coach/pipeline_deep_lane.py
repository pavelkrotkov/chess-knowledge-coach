"""Run one bounded normal-deep lane with durable pending and retry state."""

import time

from .pipeline_deep_lane_next import archive_sweep, candidate
from .pipeline_deep_lane_state import save
from .pipeline_deep_lane_step import step
from .pipeline_deep_limits import at_capacity, continue_sweep


def _expired(deadline):
    return deadline is not None and time.monotonic() >= deadline


def _start(db, config, report, state, lane, deadline):
    return None if _expired(deadline) else archive_sweep(db, config, report, state, lane)


def work(db, config, report, state, lane, seen, deadline):
    more = False
    archive = _start(db, config, report, state, lane, deadline)
    while report["examined"] < config.deep_max_scan and not at_capacity(report, config):
        if _expired(deadline):
            report["capped"] = True
            break
        item, state, more = candidate(db, config, state, lane, archive)
        save(db, config.learner, state)
        if item is None:
            break
        state, proceed = step(db, config, report, state, lane, item, archive, seen, deadline)
        save(db, config.learner, state)
        if not continue_sweep(lane, more, proceed):
            break
    if at_capacity(report, config) and more:
        report["capped"] = True
    return state, more
