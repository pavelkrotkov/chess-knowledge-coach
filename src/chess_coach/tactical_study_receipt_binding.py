"""Bind a verified private receipt to the course hash and learner."""

from datetime import datetime


def valid(state, course_hash, learner):
    flags = ("complete", "privacy_verified", "anonymous_verified", "ordered_verified")
    return (
        state.get("learner_key") == learner
        and state.get("course_sha256") == course_hash
        and all(state.get(key) is True for key in flags)
    )


def timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False
