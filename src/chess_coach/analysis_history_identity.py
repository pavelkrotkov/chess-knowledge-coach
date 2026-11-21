"""Bound and compare canonical shared-analysis profile identities."""

from .analysis_history_pages import overflow
from .fact_fingerprint import canonical, digest

MAX_PROFILE_BYTES = 1024 * 1024
MAX_DISTINCT = 4096
MAX_DISTINCT_BYTES = 32 * 1024 * 1024


class Limit(Exception):
    """The bounded inventory cannot establish a complete result."""


def bytesize(value):
    if not isinstance(value, str):
        raise Limit("unsupported stored value")
    return len(value.encode("utf-8"))


def profile(state, parts, expected=None):
    sizes = [bytesize(value) for value in parts]
    if sum(sizes) > MAX_PROFILE_BYTES:
        raise Limit("profile exceeds inventory limit")
    encoded = canonical(list(parts))
    key = digest(encoded)
    if expected is not None and expected != key:
        raise Limit("stored profile identity conflict")
    # A digest collision must fail just as the existing shared-profile writer does.
    previous = state["identities"].get(key)
    if previous is not None and previous != encoded:
        raise Limit("profile identity conflict")
    if previous is None:
        _add(state, key, encoded, sum(sizes))
    return key, sum(sizes)


def _add(state, key, encoded, raw_bytes):
    encoded_bytes = len(encoded.encode("utf-8"))
    memory = state["identity_bytes"] + encoded_bytes + 256
    if len(state["identities"]) >= MAX_DISTINCT or memory > MAX_DISTINCT_BYTES:
        raise Limit("distinct profile limit")
    state["identities"][key] = encoded
    state["identity_bytes"] = memory
    state["profile_encoded_bytes"] += encoded_bytes
    state["profile_text_bytes"] += raw_bytes
    state["profile_overflow_pages"] += overflow(320 + raw_bytes)
