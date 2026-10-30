"""Apply only explicitly bound fork-line subsets to a session snapshot."""

from . import (
    related_fork_avoidance_contract,
    related_fork_prevention_contract,
    related_mate,
    related_pin_contract,
)
from .related_fork_lines import select_lines
from .related_protection_contract import FILTER_VERSION as PROTECTION_FILTER


def apply_filter(snapshot, provenance, provenance_key, line_filter):
    if provenance_key in {
        "related_fork",
        "related_protection",
        "related_fork_prevention",
        "related_fork_avoidance",
        "related_mate",
        "related_pin",
    }:
        version = {
            "related_protection": PROTECTION_FILTER,
            "related_fork_prevention": related_fork_prevention_contract.FILTER_VERSION,
            "related_fork_avoidance": related_fork_avoidance_contract.FILTER_VERSION,
            "related_mate": related_mate.FILTER_VERSION,
            "related_pin": related_pin_contract.FILTER_VERSION,
        }.get(provenance_key)
        select_lines(snapshot, provenance, expected_version=version)
        if snapshot["lines"] != line_filter:
            raise ValueError("practice line selection unavailable")
        if provenance_key == "related_pin":
            snapshot["objective"] = "legal_line"
        if provenance_key == "related_mate":
            snapshot["objective"] = "checkmate"
    elif line_filter is not None:
        raise ValueError("unsupported practice line selection")
