"""Recheck owned-fork evidence through the shared lineage validator."""

from . import unified_fork_learning
from .mastery_unified_capture import lineage as owned_lineage


def lineage(db, evidence, completion, row):
    return owned_lineage(db, evidence, completion, row, policy=unified_fork_learning)
