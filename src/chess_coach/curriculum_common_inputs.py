"""Observe exact candidate and recorded-practice inputs for a common choice."""

from .curriculum_capture_inputs import current as capture_inputs
from .curriculum_capture_inputs import file_identity as capture_files
from .curriculum_capture_witnesses import candidates
from .curriculum_common_practice import observe as practice_inputs
from .curriculum_common_practice import selected as selected_attempts
from .curriculum_cursor import revision
from .curriculum_fork_source import read as fork_source
from .fact_fingerprint import canonical, digest
from .fork_game_trend_paths import location as fork_trend
from .fork_miss_store import location as fork_misses
from .opening_study_source import fingerprint

POLICY = "common-choice-inputs-v1"


def file_identity(db, subject, root):
    paths = [fork_trend(db, root), fork_misses(db, root)]
    if any(path is None for path in paths):
        raise ValueError("fork report scope unavailable")
    return digest(canonical([capture_files(db, subject, root), fingerprint(paths)]))


def observe(db, subject, corpus, root, as_of, check):
    before = file_identity(db, subject, root)
    capture = capture_inputs(db, subject, root, check)
    options, status, identity, advisory = candidates(
        db, subject, corpus, check, include_snapshot=True, as_of=as_of
    )
    fork, fork_status, focus = fork_source(
        db, subject, corpus, check, include_snapshot=True, as_of=as_of
    )
    attempts = selected_attempts(db, subject, corpus, options, fork, as_of, check)
    practice = practice_inputs(db, subject, corpus, attempts, check)
    check()
    if file_identity(db, subject, root) != before:
        raise ValueError("fork reports changed; restart the plan")
    value = digest(
        canonical(
            [
                POLICY,
                before,
                capture,
                status,
                identity,
                fork_status,
                fork["binding"] if fork else None,
                practice,
            ]
        )
    )
    bundle = {
        "options": options,
        "identity": identity,
        "advisory": advisory,
        "fork": fork,
        "fork_status": fork_status,
        "fork_focus": focus,
        "files": before,
        "capture": capture,
        "practice": practice,
        "attempts": attempts,
        "revision": revision(db),
    }
    return value, bundle


def current(db, subject, corpus, root, as_of, check):
    return observe(db, subject, corpus, root, as_of, check)[0]


def offer_current(db, owner, binding, root, check):
    files = file_identity(db, owner, root)
    actual = current(db, owner, binding["corpus_version"], root, binding["as_of"], check)
    if actual != binding["common_input"] or files != file_identity(db, owner, root):
        raise ValueError("common practice offer changed")
    return files
