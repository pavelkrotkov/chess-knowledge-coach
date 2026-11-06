"""Run at most one private opening comparison after ordinary pipeline work."""

import os
import time

from .opening_measure_prepare import _prepare
from .opening_queue_artifact import path
from .opening_queue_failure import record
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_previous import finished
from .opening_queue_validate import valid
from .opening_queue_write import write
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline


def run(db, config, root):
    directory, database = location(db, root, config.learner)
    with lock(directory):
        slot_path = directory / "opening-comparison-slot.json"
        item = read(slot_path)
        if item is None or not valid(item, database) or item["state"] != "queued":
            return
        if finished(directory, item):
            return
        _execute(db, config, directory, slot_path, item)


def _execute(db, config, directory, slot_path, item):
    source = item["source"]
    try:
        _prepare(
            db,
            source["game_id"],
            source["position_id"],
            source["alternative"],
            path(directory, item),
            config.engine_path,
            learner=config.learner,
            expected=(source, item["configuration"]),
        )
    except (ValueError, OSError, KeyError, TypeError, PreviewUnavailable, PreviewDeadline):
        _unavailable(directory, slot_path, item)
    except RuntimeError as error:
        if str(error) != "deep worker is already running":
            _unavailable(directory, slot_path, item)


def _unavailable(directory, slot_path, item):
    record(directory, item)
    write(slot_path, {**item, "state": "unavailable"})


def after_pipeline(db, config, started):
    # Reserve the full 25-second measurement budget and service shutdown headroom.
    if not config.deep_enabled or time.monotonic() - started > 29 * 60:
        return
    try:
        run(db, config, os.environ.get("CHESS_PROJECT_ROOT"))
    except (Exception, PreviewDeadline):
        return
