"""Resolve owner-bound review sources with their current certificates."""

from .curriculum_capture_reference import candidate as capture_candidate
from .curriculum_fork_reference import candidate as fork_candidate
from .unified_training_owned_capture import SOURCE as CAPTURE_SOURCE
from .unified_training_owned_fork import SOURCE as FORK_SOURCE


def candidate(db, row, ref):
    if row["source_type"] == CAPTURE_SOURCE:
        return True, capture_candidate(db, row, ref)
    if row["source_type"] == FORK_SOURCE:
        return True, fork_candidate(db, row, ref)
    return None
