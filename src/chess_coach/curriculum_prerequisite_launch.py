"""Revalidate a signed prerequisite diagnostic at its learning launch."""

import time

from .curriculum_cursor import revision
from .curriculum_prerequisite_mate import prompt
from .curriculum_prerequisite_source import POLICY, context, graph
from .curriculum_prerequisite_token import _decode
from .fact_fingerprint import digest
from .learner_identity import normalize_identity
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def validate(db, subject, version, key, token, check):
    subject = normalize_identity(subject)
    if subject is None:
        raise ValueError("diagnostic owner unavailable")
    data = _decode(db, token)
    policy, graph_hash, scope, owner, source_version, source_key, prompt_hash, rev, limit = data
    if (policy, graph_hash, owner, source_version, source_key, rev) != (
        POLICY,
        graph(),
        digest(subject),
        version,
        key,
        revision(db),
    ):
        raise ValueError("diagnostic binding changed")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("diagnostic limit unavailable")
    # Recheck inside the start transaction, including file-backed exposure intents.
    current = context(db, subject, limit, check)
    if current["state"] != "available" or current["scope"] != scope:
        raise ValueError("diagnostic topic changed")
    check()
    if digest(prompt(db, subject, version, key)) != prompt_hash:
        raise ValueError("diagnostic source changed")
    check()


def validate_start(db, subject, version, key, token, budget):
    expires = time.monotonic() + SLICE_SECONDS

    def check():
        budget.check()
        if time.monotonic() >= expires:
            raise PreviewUnavailable("diagnostic launch deferred")

    try:
        with budget.scope(snapshot=False):
            validate(db, subject, version, key, token, check)
    except PreviewUnavailable:
        raise ValueError("diagnostic launch unavailable") from None
