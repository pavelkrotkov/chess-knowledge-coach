"""Check the artifact identity associated with a Study intent."""

import re

from .tactical_study_receipt import NAME

OPENING = re.compile(r"opening-study-([0-9a-f]{64})-intent\.json")


def _hash(state):
    value = state.get("course_sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Study exposure unavailable")
    return value


def kind(path, state):
    if not isinstance(state, dict):
        raise ValueError("Study exposure unavailable")
    course_hash = _hash(state)
    for kind, pattern in (("tactical", NAME), ("opening", OPENING)):
        match = pattern.fullmatch(path.name)
        if match:
            if kind == "tactical" and course_hash != match.group(1):
                raise ValueError("Study exposure unavailable")
            return kind, match.group(1)
    if path.name == "poc-study-336-intent.json":
        return "legacy", None
    raise ValueError("Study exposure unavailable")
