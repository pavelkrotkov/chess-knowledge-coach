"""Run at most one explicitly requested private Study after local work."""

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .opening_study_request import SLOT, credentials, valid
from .opening_study_session import publish_locked as publish_revision
from .opening_unfamiliar_study import publish_locked
from .study_remote import StudyError
from .tactical_course_deadline import PreviewDeadline


def _publish(root, item):
    selection = item["selection"]
    if "game_id" in selection:
        return publish_revision(
            root,
            selection["game_id"],
            selection["position_id"],
            selection["move"],
            item["version"],
            queued=True,
        )
    return publish_locked(root, item["version"], selection, queued=True)


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
            _publish(root, item)
        except StudyError:
            write(slot, {**item, "state": "incomplete"})
        except ValueError:
            write(slot, {**item, "state": "stale"})
        except (Exception, PreviewDeadline):
            write(slot, {**item, "state": "incomplete"})
        else:
            write(slot, {**item, "state": "complete"})
        return True
