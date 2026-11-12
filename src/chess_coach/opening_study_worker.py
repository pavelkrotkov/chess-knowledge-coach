"""Run at most one explicitly requested private Study after local work."""

import os
import time

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .opening_study_request import SLOT, credentials, valid
from .opening_unfamiliar_study import publish_locked
from .study_remote import StudyError
from .tactical_course_deadline import PreviewDeadline


def run(db, learner, root):
    directory, database = location(db, root, learner)
    with lock(directory):
        slot = directory / SLOT
        item = read(slot)
        if not valid(item, database, learner) or item["state"] in {"stale", "complete"}:
            return
        if not credentials(root, db, learner, item["version"]):
            return
        try:
            publish_locked(root, item["version"], item["selection"], queued=True)
        except StudyError:
            write(slot, {**item, "state": "incomplete"})
        except ValueError:
            write(slot, {**item, "state": "stale"})
        except (Exception, PreviewDeadline):
            write(slot, {**item, "state": "incomplete"})
        else:
            write(slot, {**item, "state": "complete"})


def after_pipeline(db, learner, started):
    # The whole course has 60 seconds, including a hard provider deadline.
    if time.monotonic() - started > 28 * 60:
        return
    try:
        run(db, learner, os.environ.get("CHESS_PROJECT_ROOT"))
    except (Exception, PreviewDeadline):
        return
