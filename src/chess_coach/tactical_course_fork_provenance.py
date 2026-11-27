"""Retain a worker's fork assessment independently from course envelopes."""

from pathlib import Path

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .opening_public_proof import PUBLICATION_WORKING
from .opening_public_proof_files import latest, publish
from .opening_queue_location import location
from .opening_queue_lock import lock
from .opening_recent_capacity import check as capacity
from .tactical_course import FORK_VERSIONS
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
    chapters = course["preview"]["chapters"]
    if (
        course["kind"] not in FORK_VERSIONS
        or len(chapters) < 2
        or chapters[-1]["source"]["type"] != "corpus"
    ):
        return
    directory, key, assessment = _record(db, root, subject, chapters[-1])
    capacity(root, directory, deadline=budget.expires, working=PUBLICATION_WORKING)
    with lock(directory), budget.publication():
        publish(directory, key, assessment, budget.check, prefix=PREFIX)


def require(db, subject, chapter):
    directory, key, assessment = _record(db, db.capture_root, subject, chapter)
    if latest(directory, key, prefix=PREFIX) != assessment:
        raise ValueError("fork assessment preparation unavailable or changed")


def current(root, database, subject, corpus, envelope, version, kind):
    if kind not in FORK_VERSIONS:
        return
    from .tactical_study_current import revalidate

    try:
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
