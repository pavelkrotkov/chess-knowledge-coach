"""Resolve current line-filter versions for source-bound transfers."""

from . import (
    related_backrank_contract,
    related_fork_avoidance_contract,
    related_fork_lines,
    related_fork_prevention_contract,
    related_mate,
    related_pin_contract,
)
from .related_created_contract import FILTER_VERSION as CREATED_FILTER
from .related_discovery_contract import FILTER_VERSION as DISCOVERY_FILTER
from .related_protection_contract import FILTER_VERSION as PROTECTION_FILTER

_FIXED = {
    "created_exposure": CREATED_FILTER,
    "discovery_mate": DISCOVERY_FILTER,
    "backrank_attack": related_backrank_contract.FILTER_VERSION,
    "protection": PROTECTION_FILTER,
    "fork_avoidance": related_fork_avoidance_contract.FILTER_VERSION,
    "fork_prevention": related_fork_prevention_contract.FILTER_VERSION,
    "mate": related_mate.FILTER_VERSION,
}


def filter_version(motif, version=None):
    if motif == "backrank_defense":
        return related_backrank_contract.defense_filter(version)
    if motif == "pin":
        return related_pin_contract.filter_version(version)
    return _FIXED.get(motif, related_fork_lines.FILTER_VERSION)
