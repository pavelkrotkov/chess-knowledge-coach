"""Sign selected context and separately bind its eligible fork launch."""

from .curriculum_prerequisite_token import _decode, encode
from .fact_fingerprint import digest
from .learner_identity import normalize_identity

CONTEXT = "opening-context-plan-v1"
LAUNCH = "opening-context-fork-launch-v1"


def _owner(subject):
    owner = normalize_identity(subject)
    if owner is None:
        raise ValueError("opening owner unavailable")
    return digest(owner)


def issue_context(db, subject, context, scope):
    return encode(
        db,
        [
            CONTEXT,
            _owner(subject),
            context["choice"],
            context["binding"],
            scope,
            None,
            None,
            None,
            None,
        ],
    )


def context(db, subject, value):
    data = _decode(db, value)
    owner = normalize_identity(subject)
    if owner is None or data[0] != CONTEXT or data[1] != digest(owner):
        raise ValueError("opening context owner changed")
    return data


def issue_launch(db, subject, context, item, exposure, scope, revision, corpus):
    return encode(
        db,
        [
            LAUNCH,
            _owner(subject),
            context["choice"],
            context["binding"],
            item["source_version"],
            item["source_key"],
            digest(item["prompt_key"]),
            exposure,
            [scope, revision, corpus],
        ],
    )


def launch(db, subject, value):
    data = _decode(db, value)
    owner = normalize_identity(subject)
    if owner is None or data[0] != LAUNCH or data[1] != digest(owner):
        raise ValueError("opening launch owner changed")
    return data
