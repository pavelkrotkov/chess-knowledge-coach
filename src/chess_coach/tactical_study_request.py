"""Queue one exact offered tactical export for private Study publication."""

import os

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .opening_study_request_validate import credentials
from .tactical_course_offer_read import offered
from .tactical_study_slot import replaceable

SLOT = "tactical-study-request.json"


def configured(root, db, learner, corpus, version):
    return os.environ.get("CHESS_CORPUS") == corpus and credentials(root, db, learner, version)


def enqueue(db, root, learner, corpus, version):
    directory, database = location(db, root, learner)
    if not configured(root, db, learner, corpus, version):
        raise ValueError("Study credentials unavailable")
    with lock(directory):
        selected, _ = offered(root, db.path, learner, corpus)
        if selected["hash"] != version:
            raise ValueError("offered course changed")
        item = {
            "database": database,
            "owner": learner_key(learner),
            "version": version,
            "file": selected["file"],
            "corpus": corpus,
            "state": "queued",
            "turn": "opening",
        }
        slot = directory / SLOT
        previous = read(slot)
        if previous is None and (slot.exists() or slot.is_symlink()):
            raise ValueError("Study request unavailable")
        if replaceable(directory, previous, item, database, learner):
            write(slot, item)
