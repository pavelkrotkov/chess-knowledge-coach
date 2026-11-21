"""One private, owner-bound request for a locally prepared course."""

import re
import secrets

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_queue_write import write
from .tactical_course_choice import normalize
from .tactical_course_offer import PREPARE_SLOT, SLOT

VERSION = "tactical-course-request-v1"
SELECTED_VERSION = "tactical-course-request-v2"


def _selection_valid(item):
    try:
        if item.get("version") == VERSION:
            return item.get("selection") is None
        return item.get("version") == SELECTED_VERSION and (
            normalize(item.get("selection")) == item.get("selection")
        )
    except (ValueError, TypeError):
        return False


def valid(item, database, learner, corpus):
    if not isinstance(item, dict):
        return False
    request_id = item.get("id")
    identity = (item.get("version"), item.get("database"), item.get("owner"), item.get("corpus"))
    return (
        _selection_valid(item)
        and identity == (item["version"], database, learner_key(learner), corpus)
        and item.get("state") in {"queued", "running", "complete", "unavailable"}
        and isinstance(request_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", request_id) is not None
    )


def enqueue(db, root, learner, corpus, *, selected=None):
    """Coalesce pending requests; never replace an unrecognized private slot."""
    if not isinstance(corpus, str) or not corpus:
        raise ValueError("course corpus unavailable")
    # A repeated request is coalesced only when its exact selection matches.
    chosen = None if selected is None else normalize(selected)
    directory, database = location(db, root, learner)
    with lock(directory):
        slot = directory / PREPARE_SLOT
        old = read(slot)
        if _coalesced(slot, old, directory, database, learner, corpus, chosen):
            return
        # Keep legacy requests recognizable and give selected requests their own
        # version so retries preserve the chosen weaknesses exactly.
        item = {
            "version": VERSION if chosen is None else SELECTED_VERSION,
            "database": database,
            "owner": learner_key(learner),
            "corpus": corpus,
            "state": "queued",
            "id": secrets.token_hex(16),
        }
        if chosen is not None:
            item["selection"] = chosen
        write(slot, item)


def _coalesced(slot, old, directory, database, learner, corpus, chosen):
    # Never replace an unrecognized slot, or coalesce a different selection.
    if not slot.exists() and not slot.is_symlink():
        return False
    if not valid(old, database, learner, corpus):
        raise ValueError("course request unavailable")
    if old["state"] in {"queued", "running"} and _pending(old, directory):
        if old.get("selection") != chosen:
            raise ValueError("another course selection is pending")
        return True
    return False


def _pending(item, directory):
    return "offer" not in item or read(directory / SLOT) == item.get("previous_offer")


def status(db, root, learner, corpus, offered=None):
    """Read status without opening the learner database or rebuilding a course."""
    try:
        directory, database = location(db, root, learner)
        item = read(directory / PREPARE_SLOT)
        if item is None:
            return None
        if not valid(item, database, learner, corpus):
            return "unavailable"
        if offered is not None and read(directory / SLOT) != offered:
            return "unavailable"
        return _state(item, offered)
    except (OSError, ValueError, TypeError, KeyError):
        return "unavailable"


def _state(item, offered):
    # A saved completion belongs only to its matching offer. If the offer was
    # replaced, report that change instead of attributing the newer course to it.
    if item.get("offer"):
        if offered == item["offer"]:
            return "complete"
        if item["state"] == "complete" or offered != item.get("previous_offer"):
            return "superseded" if offered else "unavailable"
    return item["state"]
