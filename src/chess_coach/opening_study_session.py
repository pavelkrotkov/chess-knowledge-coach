"""Publish an exact current opening preview through the private Study ledger."""

import time
from contextlib import nullcontext
from functools import partial

from .opening_queue_lock import lock as opening_lock
from .opening_study_current import admitted
from .opening_study_freeze import freeze
from .opening_study_paths import paths as _paths
from .pipeline_network_deadline import network_deadline
from .study_publisher import publish
from .study_remote import StudyError
from .study_session import _publish, locked
from .tactical_study_intents import MAX_INTENTS, require_clear


def publish_locked(root, game, position, move, version, *, queued=False):
    root, learner, planning, database = _paths(root, version)
    with (
        locked(database, planning, sync_wait=not queued),
        nullcontext() if queued else opening_lock(planning),
        admitted(
            database, planning, root, learner, game, position, move, version, bounded=queued
        ) as source,
    ):
        if queued:
            from .opening_study_receipt import verified

            if verified(planning, learner, version, source[0]):
                source[2]()
                return
        return publish_course(database, planning, version, source, bounded=queued)


def publish_course(database, planning, version, source, *, bounded=False):
    course, budget, check = source
    destination = planning / f"opening-study-{version}-intent.json"
    existing = require_clear(planning, destination)
    if len(existing) + (destination not in existing) > MAX_INTENTS:
        raise ValueError("too many Study intents")
    check = freeze(planning / f"opening-study-{version}-course.json", course, budget, check)
    check()
    timer = (
        network_deadline(max(0.001, budget.expires - time.monotonic()))
        if bounded
        else nullcontext()
    )
    with timer:
        try:
            return _publish(
                database,
                destination,
                course,
                action=partial(publish, check=check, strict=True),
                check=check,
            )
        except ValueError:
            if not bounded:
                raise
            raise StudyError("Study publication incomplete") from None
