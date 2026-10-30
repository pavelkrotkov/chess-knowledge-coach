"""Share a bounded automatic cycle between normal and purpose work."""

import time

from .pipeline_deep import process_deep
from .pipeline_deep_config import combined_status
from .style_schedule_store import next_sequence
from .style_schedule_worker import process_schedule

CYCLE_SECONDS = 55.0
FAMILY_SECONDS = 25.0


def process_deep_cycle(db, config):
    if not config.deep_enabled:
        return process_deep(db, config), {"status": "disabled"}
    _, sequence = next_sequence(db, config.learner)
    deadline = time.monotonic() + CYCLE_SECONDS
    if sequence % 2:
        purpose = _purpose(db, config, deadline)
        normal = _normal(db, config, deadline)
    else:
        normal = _normal(db, config, deadline)
        purpose = _purpose(db, config, deadline)
    return normal, purpose


def _family_deadline(deadline):
    return min(deadline, time.monotonic() + FAMILY_SECONDS)


def _normal(db, config, deadline):
    try:
        return process_deep(db, config, deadline=_family_deadline(deadline))
    except Exception:
        return {"status": "partial", "detail": "normal_deep_unavailable", "processed": []}


def _purpose(db, config, deadline):
    if time.monotonic() >= deadline:
        return {"status": "partial", "detail": "worker_deadline"}
    try:
        return process_schedule(db, config, deadline=_family_deadline(deadline))
    except Exception:
        return {"status": "partial", "detail": "purpose_schedule_unavailable"}


def attach_status(report, purpose):
    report["status"] = combined_status(report["status"], purpose)
    report["purpose_schedule"] = purpose
    return report
