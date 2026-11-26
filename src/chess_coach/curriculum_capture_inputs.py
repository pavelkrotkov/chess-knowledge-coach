"""Bind bounded capture-practice inputs and owner-private report identities."""

from itertools import chain, islice

from .capture_game_trend_paths import location as trend_location
from .curriculum_capture_practice_binding import practice
from .fact_fingerprint import canonical, digest
from .opening_queue_location import location
from .opening_study_source import fingerprint
from .tactical_study_intents import MAX_INTENTS

POLICY = "capture-practice-inputs-v1"


def _paths(db, subject, root):
    directory, _ = location(db, root, subject)
    trend = trend_location(db, root)
    if trend is None:
        raise ValueError("capture report scope unavailable")
    paths = list(
        islice(
            chain(
                directory.glob("tactical-study-*-intent.json"),
                directory.glob("opening-study-*-intent.json"),
            ),
            MAX_INTENTS + 1,
        )
    )
    if len(paths) > MAX_INTENTS:
        raise ValueError("capture exposure scope incomplete")
    paths.extend([directory / "poc-study-336-intent.json", trend])
    return sorted(paths)


def _files(db, subject, root):
    paths = _paths(db, subject, root)
    return [[path.name, item] for path, item in zip(paths, fingerprint(paths), strict=True)]


def file_identity(db, subject, root):
    return digest(canonical(_files(db, subject, root)))


def observe(db, subject, root, check):
    """Return private digests from one stable bounded observation."""
    check()
    before = _files(db, subject, root)
    values = practice(db, subject, check)
    check()
    if before != _files(db, subject, root):
        raise ValueError("capture practice inputs changed")
    return digest(canonical([POLICY, before, values])), digest(canonical(before))


def current(db, subject, root, check):
    return observe(db, subject, root, check)[0]
