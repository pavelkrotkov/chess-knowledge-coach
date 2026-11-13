"""Dispatch at most one bounded opening or tactical Study job."""

import os
import time

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .opening_study_worker import run as opening_run
from .pipeline_cooldown import active_deadline
from .tactical_course_deadline import PreviewDeadline
from .tactical_study_request import SLOT as TACTICAL_SLOT
from .tactical_study_slot import valid as tactical_valid
from .tactical_study_worker import run as tactical_run


def _turn(directory, database, learner, original):
    with lock(directory):
        slot = directory / TACTICAL_SLOT
        item = read(slot)
        if (
            tactical_valid(item, database, learner)
            and item["state"] in {"queued", "incomplete"}
            and (item["version"], item["file"]) == (original["version"], original["file"])
        ):
            write(slot, {**item, "turn": "tactical"})


def dispatch(db, learner, root):
    if active_deadline(db, None) is not None:
        return
    directory, database = location(db, root, learner)
    item = read(directory / TACTICAL_SLOT)
    pending = tactical_valid(item, database, learner) and item["state"] in {"queued", "incomplete"}
    if pending and item["turn"] == "opening" and opening_run(db, learner, root):
        _turn(directory, database, learner, item)
        return
    if pending and tactical_run(db, learner, root):
        return
    opening_run(db, learner, root)


def after_pipeline(db, learner, started):
    # Reserve a bounded job and shutdown time within the existing worker unit.
    if time.monotonic() - started > 28 * 60:
        return
    try:
        dispatch(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
    except (Exception, PreviewDeadline):
        return
