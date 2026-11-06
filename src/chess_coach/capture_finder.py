"""Find a fully certified unfamiliar capture on explicit request."""

import time

from .capture_finder_scope import restrict, validate
from .capture_finder_search import search
from .capture_plan_sources import _groups
from .learner_identity import normalize_identity
from .related_capture_familiar import familiarity

SECONDS = 90.0


def _expired(deadline):
    return time.monotonic() >= deadline


def find(db, subject, corpus, secret, *, position=None):
    learner = normalize_identity(subject)
    if not learner or secret is None:
        raise ValueError("capture finder unavailable")
    validate(position)
    deadline = time.monotonic() + SECONDS
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    if _expired(deadline):
        return None
    groups, _, _ = _groups(db, learner)
    groups = restrict(groups, position)
    found = None
    if groups and not _expired(deadline):
        familiar = familiarity(db, subject)
        if not _expired(deadline):
            found = search(
                db, learner, subject, corpus, secret, groups, familiar, deadline, _expired
            )
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture sources changed")
    return found
