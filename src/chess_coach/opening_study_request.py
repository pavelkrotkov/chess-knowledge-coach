"""Retain one explicitly requested, exact private opening Study."""

import os

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import staged, sync
from .opening_study_receipt import verified
from .opening_study_request_prior import unchanged
from .opening_study_request_validate import credentials, valid
from .opening_study_session import _paths
from .opening_unfamiliar_study_current import admitted

SLOT = "opening-study-request.json"


def enqueue(db, root, learner, version, selection):
    directory, database = location(db, root, learner)
    if not credentials(root, db, learner, version):
        raise ValueError("Study credentials unavailable")
    item = {
        "database": database,
        "owner": learner_key(learner),
        "version": version,
        "selection": selection,
        "state": "queued",
    }
    if not valid(item, database, learner):
        raise ValueError("Study selection unavailable")
    root, _, _, database_path = _paths(root, version)
    with admitted(database_path, directory, root, learner, version, selection) as source:
        course, budget, check = source
        with lock(directory):
            check()
            if verified(directory, learner, version, course):
                return
            slot = directory / SLOT
            old = read(slot)
            if unchanged(old, item, database, learner, directory):
                return
            with staged(slot, item) as temporary, budget.publication():
                check()
                os.replace(temporary, slot)
            sync(directory)
