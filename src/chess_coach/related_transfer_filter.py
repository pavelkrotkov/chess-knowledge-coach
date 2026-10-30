"""Resolve current line-filter versions for source-bound transfers."""

from . import (
    related_fork_avoidance_contract,
    related_fork_lines,
    related_fork_prevention_contract,
    related_mate,
)
from .related_protection_contract import FILTER_VERSION as PROTECTION_FILTER


def filter_version(motif):
    if motif == "protection":
        return PROTECTION_FILTER
    if motif == "fork_avoidance":
        return related_fork_avoidance_contract.FILTER_VERSION
    if motif == "fork_prevention":
        return related_fork_prevention_contract.FILTER_VERSION
    if motif == "mate":
        return related_mate.FILTER_VERSION
    return related_fork_lines.FILTER_VERSION
