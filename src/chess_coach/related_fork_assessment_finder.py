"""Find one source-bound unfamiliar fork with a bounded certificate search."""

import time

from .fork_difficulty_selection import selection_options
from .fork_followup_search import accept_options
from .recurrence_cursor import _valid_id
from .related_capture import present
from .related_fork import selection
from .related_fork_assessment_search import search

SECONDS = 40


def find(
    db,
    subject,
    evidence_id,
    corpus_version,
    secret,
    *,
    expected=None,
    started=None,
    difficulty=None,
):
    if not _valid_id(evidence_id):
        return None
    started = time.monotonic() if started is None else started
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    selected = selection(db, subject, evidence_id, corpus_version, **selection_options(difficulty))
    if selected is None or selected[0]["outcome"] != "failure" or secret is None:
        return None
    item = search(db, selected[3], started, SECONDS, **accept_options(db, expected))
    if item is None:
        return None
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("fork selection changed")
    return present((*selected[:3], [item], *selected[4:]), None, secret=secret)
