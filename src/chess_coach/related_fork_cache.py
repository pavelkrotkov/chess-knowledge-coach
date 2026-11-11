"""Reuse a fork source only within a caller-owned checked request."""

from .related_fork_source import source_for_evidence


def source(db, row, binding, cache, check):
    key = ("fork", row["subject"], binding["evidence_id"])
    if cache is not None and key in cache:
        return cache[key]
    source = source_for_evidence(db, row["subject"], binding["evidence_id"], check=check)
    if cache is not None:
        cache[key] = source
    return source
