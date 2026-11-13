"""Atomically claim and finish one local course request."""

from .opening_queue_files import read
from .opening_queue_lock import lock
from .opening_queue_write import write
from .tactical_course_offer import PREPARE_SLOT, SLOT, _offer_locked
from .tactical_course_offer import item as offer_item
from .tactical_course_request import valid


def claim(directory, database, learner, corpus):
    """Capture the current offer and release the lock before building."""
    with lock(directory):
        slot = directory / PREPARE_SLOT
        item = read(slot)
        if not valid(item, database, learner, corpus) or item["state"] not in {"queued", "running"}:
            return None
        # The expensive build runs without holding the shared planning lock.
        old_offer = read(directory / SLOT)
        write(slot, {**item, "state": "running"})
        return item, old_offer


def finish(directory, database, learner, corpus, requested, old_offer, result, path, budget):
    """Publish only if neither the request nor the offered course changed."""
    with lock(directory):
        slot = directory / PREPARE_SLOT
        current = read(slot)
        if not valid(current, database, learner, corpus) or current["id"] != requested["id"]:
            raise ValueError("course request changed")
        # A concurrent manual offer wins; never silently replace a newer course.
        if read(directory / SLOT) != old_offer:
            raise ValueError("course offer changed")
        _offer_locked(directory, offer_item(database, learner, path, result), budget)
        write(slot, {**current, "state": "complete"})


def failed(directory, database, learner, corpus, requested):
    with lock(directory):
        slot = directory / PREPARE_SLOT
        current = read(slot)
        if valid(current, database, learner, corpus) and current["id"] == requested["id"]:
            write(slot, {**current, "state": "unavailable"})
