"""Share one bounded private Study job between opening and tactical requests."""

from pathlib import Path

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .study_remote import StudyError
from .tactical_course_deadline import PreviewDeadline
from .tactical_export_input import load
from .tactical_study_part import receipt, select
from .tactical_study_preview import preview
from .tactical_study_request import SLOT, configured
from .tactical_study_session import publish_locked
from .tactical_study_slot import valid


def run(db, learner, root):
    root = Path(root)
    directory, database = location(db, root, learner)
    with lock(directory):
        slot = directory / SLOT
        item = read(slot)
        if not valid(item, database, learner) or item["state"] not in {"queued", "incomplete"}:
            return False
        if not configured(root, db, learner, item["corpus"], item["version"]):
            return False
        state = _publish(root, directory, learner, item)
        write(slot, {**item, "state": state, "turn": "opening"})
        return True


def _publish(root, directory, learner, item):
    try:
        envelope = load(root, directory / item["file"])
        preview(envelope, item["version"])
        part = item.get("part")
        target = select(envelope["export"], item["version"], part)
        if not receipt(directory, learner, target):
            options = {"part": part} if part is not None else {}
            publish_locked(root, directory / item["file"], item["version"], queued=True, **options)
        if not receipt(directory, learner, target):
            return "incomplete"
    except StudyError:
        return "incomplete"
    except ValueError:
        return "stale"
    except (Exception, PreviewDeadline):
        return "incomplete"
    return "complete"
