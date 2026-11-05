"""Bind a verified private receipt to the course hash and learner."""


def valid(state, course_hash, learner):
    flags = ("complete", "privacy_verified", "anonymous_verified", "ordered_verified")
    return (
        state.get("learner_key") == learner
        and state.get("course_sha256") == course_hash
        and all(state.get(key) is True for key in flags)
    )
