"""Publish a reviewed unfamiliar-opening course through the private Study ledger."""

import os
from contextlib import nullcontext

from .opening_queue_lock import lock as opening_lock
from .opening_study_receipt import verified
from .opening_study_session import _paths, publish_course
from .opening_unfamiliar_study_current import admitted
from .study_session import locked


def publish_locked(root, version, selection=None, *, queued=False):
    root, learner, planning, database = _paths(root, version)
    if not os.environ.get("LICHESS_STUDY_TOKEN", "").strip():
        raise ValueError("Study credentials unavailable")
    with (
        locked(database, planning, sync_wait=not queued),
        nullcontext() if queued else opening_lock(planning),
        admitted(database, planning, root, learner, version, selection) as source,
    ):
        if queued and verified(planning, learner, version, source[0]):
            source[2]()
            return
        return publish_course(database, planning, version, source, bounded=queued)
