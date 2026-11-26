"""Bind a selected capture review to its signed preselection observation."""

import time
from datetime import UTC, datetime

from .capture_certificate_store import scope
from .curriculum_capture_file_guard import current
from .curriculum_cursor import revision
from .curriculum_cursor_codec import decode_cursor
from .curriculum_due import due_candidate
from .curriculum_priority_cursor import CAPTURE_FILE_POLICIES, CONTEXT_CAPTURE_POLICY
from .curriculum_window_cursor import decode
from .fact_fingerprint import digest
from .learner_identity import normalize_identity
from .objective_capture_contract import VERSIONS
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def _state(db, cursor):
    try:
        value = decode(db, cursor)
    except ValueError:
        state = decode_cursor(db, cursor)
        if not state.get("capture_selection"):
            raise ValueError("practice selection unavailable") from None
        return state
    # A window selection may remain usable after expiry only for actual due work.
    if not value["selection_only"]:
        raise ValueError("practice selection unavailable")
    return value["state"]


def _requested(cursor, source, version, item_id):
    return bool(cursor and item_id is not None and source == "own-game" and version in VERSIONS)


def prepare(db, root, cursor, corpus, subject, source, version, key, item_id, training):
    db.capture_root = scope(root, db.capture_root)
    if not _requested(cursor, source, version, item_id):
        return None
    state = _state(db, cursor)
    owner = normalize_identity(subject)
    if not owner or state.get("priority_policy") not in CAPTURE_FILE_POLICIES or not training:
        raise ValueError("capture practice changed; restart the plan")
    if (state["subject_hash"], state["corpus_version"]) != (digest(owner), corpus) or root is None:
        raise ValueError("capture practice changed; restart the plan")
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SLICE_SECONDS)
    selected = {
        "owner": owner,
        "root": root,
        "files": state["capture_files"],
        "context": state["priority_policy"] == CONTEXT_CAPTURE_POLICY,
        "item": item_id,
        "revision": state["revision"],
        "version": version,
        "key": key,
        "budget": budget,
    }
    finish(db, selected)
    return selected


# SQLite's write lock does not freeze the worker's sidecar publications.
def _current(db, selected):
    return selected["files"] == current(
        db, selected["owner"], selected["root"], context=selected["context"]
    )


def _due(db, selected):
    row = db.connection.execute(
        "SELECT id,source_type,source_ref,due FROM training_items WHERE id=?", (selected["item"],)
    ).fetchone()
    if row is None:
        return False
    candidate = due_candidate(db, row, datetime.now(UTC), digest(selected["owner"]))
    return candidate is not None and (
        candidate["source_type"],
        candidate["source_version"],
        candidate["source_key"],
    ) == ("own-game", selected["version"], selected["key"])


# Check the scheduled source and revision before the transaction creates a session.
def validate(db, selected):
    if selected is None:
        return
    try:
        with selected["budget"].scope(snapshot=False):
            if (
                revision(db) != selected["revision"]
                or not _current(db, selected)
                or not _due(db, selected)
            ):
                raise ValueError("capture practice changed; restart the plan")
    except PreviewUnavailable:
        raise ValueError("capture practice changed; restart the plan") from None


# Enrollment can change the revision; only external files are rechecked at commit.
def finish(db, selected):
    if selected is None:
        return
    try:
        with selected["budget"].scope(snapshot=False):
            if not _current(db, selected):
                raise ValueError("capture practice changed; restart the plan")
    except PreviewUnavailable:
        raise ValueError("capture practice changed; restart the plan") from None
