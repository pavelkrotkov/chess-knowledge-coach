"""Match a prospective capture against the same validated cohort."""

import json

from .capture_compare_signature import signature
from .fact_fingerprint import canonical
from .related_capture_assessment_context import capture


def matches(db, selection, candidate, expected):
    if candidate["type"] != "corpus":
        return False
    try:
        context = capture(db, candidate["version"], candidate["key"], *selection[:3])
        # Admission persists JSON, so normalize tuples before applying that same policy.
        stored = json.loads(canonical(context))
        return signature(stored, candidate["version"]) == expected
    except (ValueError, TypeError, KeyError, IndexError):
        return False
