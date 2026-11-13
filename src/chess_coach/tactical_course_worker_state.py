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
        if "offer" in item:
            if old_offer == item["offer"]:
                return None
            if old_offer != item.get("previous_offer"):
                write(slot, {**item, "state": "unavailable"})
                return None
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
        intended = offer_item(database, learner, path, result)
        if intended == old_offer:
            raise ValueError("course offer identity is unchanged")
        pending = {**current, "offer": intended, "previous_offer": old_offer}
        write(slot, pending)
        _offer_locked(directory, intended, budget)
        write(slot, {**pending, "state": "complete"})


def failed(directory, database, learner, corpus, requested):
    with lock(directory):
        slot = directory / PREPARE_SLOT
        current = read(slot)
        if valid(current, database, learner, corpus) and current["id"] == requested["id"]:
            if current.get("offer") and read(directory / SLOT) == current["offer"]:
                return
            write(slot, {**current, "state": "unavailable"})
