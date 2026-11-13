"""One private, owner-bound request for a locally prepared course."""

import re
import secrets

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .tactical_course_offer import PREPARE_SLOT

VERSION = "tactical-course-request-v1"


def valid(item, database, learner, corpus):
    if not isinstance(item, dict):
        return False
    request_id = item.get("id")
    identity = (item.get("version"), item.get("database"), item.get("owner"), item.get("corpus"))
    return (
        identity == (VERSION, database, learner_key(learner), corpus)
        and item.get("state") in {"queued", "running", "complete", "unavailable"}
        and isinstance(request_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", request_id) is not None
    )


def enqueue(db, root, learner, corpus):
    """Coalesce pending requests; never replace an unrecognized private slot."""
    if not isinstance(corpus, str) or not corpus:
        raise ValueError("course corpus unavailable")
    directory, database = location(db, root, learner)
    with lock(directory):
        slot = directory / PREPARE_SLOT
        old = read(slot)
        # An invalid or legacy slot may contain user data; never replace it.
        if old is not None or slot.exists() or slot.is_symlink():
            if not valid(old, database, learner, corpus):
                raise ValueError("course request unavailable")
            # Multiple clicks represent one pending preparation, not more jobs.
            if old["state"] in {"queued", "running"}:
                return
        write(
            slot,
            {
                "version": VERSION,
                "database": database,
                "owner": learner_key(learner),
                "corpus": corpus,
                "state": "queued",
                "id": secrets.token_hex(16),
            },
        )


def status(db, root, learner, corpus):
    """Read status without opening the learner database or rebuilding a course."""
    try:
        directory, database = location(db, root, learner)
        item = read(directory / PREPARE_SLOT)
        if item is None:
            return None
        return item["state"] if valid(item, database, learner, corpus) else "unavailable"
    except (OSError, ValueError, TypeError, KeyError):
        return "unavailable"
