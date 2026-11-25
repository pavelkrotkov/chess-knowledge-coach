"""Recheck an owner-bound plan offer at its actual launch."""

from . import curriculum_window_scope
from .curriculum_cursor import revision
from .curriculum_prerequisite_token import _decode
from .curriculum_window_scope import GOALS, POLICY
from .fact_fingerprint import digest
from .learner_identity import normalize_identity
from .mastery_time import parse_utc


def valid_time(data):
    if data[3] is None:
        return
    deadline = parse_utc(data[3])
    if deadline is None or curriculum_window_scope.clock() >= deadline:
        raise ValueError("practice window expired")


def check(db, token, subject, source, version, key, mode):
    data = _decode(db, token)
    owner = normalize_identity(subject)
    if (
        owner is None
        or data[0] != POLICY
        or data[1] != digest(owner)
        or not isinstance(data[2], str)
        or data[2] not in GOALS
    ):
        raise ValueError("practice window scope changed")
    if (data[4], data[5], data[6], data[7], data[8]) != (source, version, key, revision(db), mode):
        raise ValueError("practice window offer changed")
    valid_time(data)
    return data
