"""Retain a worker's fork assessment independently from course envelopes."""

from pathlib import Path

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .opening_public_proof import PUBLICATION_WORKING
from .opening_public_proof_files import latest, publish
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_recent_capacity import check as capacity
from .tactical_course import (
    DEFAULT_PROTECTION_ROLES_VERSION,
    MATE_ROLE_VERSIONS,
    MIXED_SELECTED_VERSION,
    QUALIFIED_FORK_VERSIONS,
)
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline

PREFIX = "tactical-fork-proof"
POLICY = "selected-course-fork-proof-v1"


def _record(db, root, subject, chapter):
    directory, database = location(db, root, subject)
    source = chapter["source"]
    assessment = source["binding"]["assessment"]
    key = digest(canonical([POLICY, database, learner_key(subject), source]))
    return directory, key, assessment


def retain(db, root, subject, course, budget):
    if course["kind"] not in QUALIFIED_FORK_VERSIONS:
        return
    # A mixed course can end with another family's practice; retain the fork's proof.
    chapter = next(
        (
            item
            for item in course["preview"]["chapters"]
            if item["source"]["type"] == "corpus"
            and item["source"].get("binding", {}).get("motif") == "fork"
        ),
        None,
    )
    if chapter is None:
        return
    directory, key, assessment = _record(db, root, subject, chapter)
    capacity(root, directory, deadline=budget.expires, working=PUBLICATION_WORKING)
    with lock(directory), budget.publication():
        publish(directory, key, assessment, budget.check, prefix=PREFIX)


def require(db, subject, chapter):
    directory, key, assessment = _record(db, db.capture_root, subject, chapter)
    if latest(directory, key, prefix=PREFIX) != assessment:
        raise ValueError("fork assessment preparation unavailable or changed")


def current(root, database, subject, corpus, envelope, version, kind):
    if kind not in QUALIFIED_FORK_VERSIONS:
        return
    try:
        if kind in {DEFAULT_PROTECTION_ROLES_VERSION, MIXED_SELECTED_VERSION, *MATE_ROLE_VERSIONS}:
            from .tactical_course_fork_read import current as fork_current

            try:
                return fork_current(root, database, subject, corpus, envelope, version)
            except PreviewUnavailable:
                raise ValueError("fork course currentness unavailable") from None
        from .tactical_study_current import revalidate

        with revalidate(
            Path(database).resolve(strict=True),
            envelope,
            version,
            project_root=root,
            subject=subject,
            corpus=corpus,
        ):
            pass
    except PreviewDeadline:
        raise ValueError("fork course currentness unavailable") from None
