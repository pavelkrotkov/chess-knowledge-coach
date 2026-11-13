"""Offer one exact, privately exported tactical course to its learner."""

import os
from datetime import UTC, datetime
from types import SimpleNamespace

from .deep_selection_source import learner_key
from .opening_queue_location import location
from .opening_queue_write import staged, sync

SLOT = "tactical-course-offer.json"
VERSION = "tactical-course-offer-v1"


def offer(root, database, subject, output, export, budget, *, enabled):
    if not enabled:
        return
    directory, identity = location(SimpleNamespace(path=database), root, subject)
    item = {
        "version": VERSION,
        "database": identity,
        "owner": learner_key(subject),
        "file": output.name,
        "hash": export["export_sha256"],
        "prepared_at": datetime.now(UTC).isoformat(),
    }
    with staged(directory / SLOT, item) as temporary, budget.publication():
        os.replace(temporary, directory / SLOT)
    sync(directory)
