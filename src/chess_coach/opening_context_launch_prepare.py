"""Preflight an exact related fork before the launch transaction."""

import sqlite3

from .curriculum_cursor import revision
from .opening_context_launch_guard import begin, validate
from .opening_context_launch_offer_scope import offer as offer_scope
from .opening_context_launch_preflight import preflight
from .opening_context_launch_task import bind
from .opening_context_launch_token import launch
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline


def prepare(
    db, root, subject, token, window, window_cursor, source, version, key, training, item_id
):
    if token is None:
        return None
    try:
        return _prepare(
            db, root, subject, token, window, window_cursor, source, version, key, training, item_id
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OSError,
        sqlite3.Error,
        PreviewUnavailable,
        PreviewDeadline,
    ):
        raise ValueError("opening experiment unavailable or changed") from None


def _prepare(
    db, root, subject, token, window, window_cursor, source, version, key, training, item_id
):
    data = launch(db, subject, token)
    if (source, training, item_id, version, key) != ("own-game", True, None, data[4], data[5]):
        raise ValueError("opening task changed")
    scope, expected_revision, corpus = data[8]
    if (
        offer_scope(db, window, window_cursor, data[1]) != scope
        or revision(db) != expected_revision
    ):
        raise ValueError("opening plan changed")
    current = preflight(db, root, subject, data[2])
    if current["binding"] != data[3]:
        raise ValueError("opening context changed")
    from .curriculum_capture_offer import COMMON_WINDOW_POLICY, token_policy

    if token_policy(db, window) == COMMON_WINDOW_POLICY:
        begin(current)
    current["task"] = bind(db, subject, current, corpus, data, version, key)
    validate(current, db, root, subject)
    begin(current)
    return current


def check(current, db, root, subject):
    if current is not None:
        validate(current, db, root, subject)
