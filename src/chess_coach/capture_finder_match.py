"""Match a prospective capture against the same validated cohort."""

import json

from .capture_compare_signature import signature
from .fact_fingerprint import canonical
from .related_capture_assessment_context import capture


def _matches(context, version, expected):
    # Admission persists JSON, so normalize tuples before applying that same policy.
    stored = json.loads(canonical(context))
    return signature(stored, version) == expected


def matches(db, selection, candidate, expected):
    if candidate["type"] != "corpus":
        return False
    try:
        context = capture(db, candidate["version"], candidate["key"], *selection[:3])
        return _matches(context, candidate["version"], expected)
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def prepared_matches(db, selection, candidate, expected, subject, games):
    from .related_capture_prepared_assessment import assessment

    if candidate["type"] != "corpus":
        return False
    try:
        proof = assessment(
            db, candidate["version"], candidate["key"], *selection[:3], subject, games
        )
        return _matches(proof["context"], candidate["version"], expected)
    except (ValueError, TypeError, KeyError, IndexError):
        return False
