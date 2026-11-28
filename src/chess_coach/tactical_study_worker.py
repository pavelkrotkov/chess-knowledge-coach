"""Share one bounded private Study job between opening and tactical requests."""

from pathlib import Path

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .study_remote import StudyError
from .tactical_course_deadline import PreviewDeadline
from .tactical_export_input import load
from .tactical_study_current import revalidate
from .tactical_study_parts import manifest, receipts
from .tactical_study_preview import preview
from .tactical_study_receipt import exact
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
        parts = manifest(envelope["export"], item["version"])
        if parts["part_count"] == 1:
            if item.get("multipart") is not None:
                raise ValueError("course parts changed")
            if not exact(directory, learner, item["version"], envelope["export"]):
                publish_locked(root, directory / item["file"], item["version"], queued=True)
        else:
            expected = {"sha256": parts["sha256"], "part_count": parts["part_count"]}
            if item.get("multipart") != expected:
                raise ValueError("course parts changed")
            remaining = next(
                (row for row in receipts(directory, learner, parts) if not row["receipt"]), None
            )
            if remaining is not None:
                publish_locked(
                    root,
                    directory / item["file"],
                    item["version"],
                    queued=True,
                    part_number=remaining["number"],
                )
            with revalidate(
                Path(item["database"][0]),
                envelope,
                item["version"],
                project_root=root,
                subject=learner,
                corpus=item["corpus"],
            ) as check:
                check()
            if any(not row["receipt"] for row in receipts(directory, learner, parts)):
                return "incomplete"
    except StudyError:
        return "incomplete"
    except ValueError:
        return "stale"
    except (Exception, PreviewDeadline):
        return "incomplete"
    return "complete"
