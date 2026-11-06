"""Apply only explicitly bound fork-line subsets to a session snapshot."""

from . import (
    related_backrank_contract,
    related_fork_avoidance_contract,
    related_fork_prevention_contract,
    related_mate,
    related_pin_contract,
)
from .related_fork_lines import select_lines
from .related_protection_contract import FILTER_VERSION as PROTECTION_FILTER
from .related_session_fork_apply import apply as apply_fork


def apply_filter(snapshot, provenance, provenance_key, line_filter):
    if provenance_key == "related_capture":
        return _capture(snapshot, provenance, line_filter)
    return _other(snapshot, provenance, provenance_key, line_filter)


def _capture(snapshot, provenance, line_filter):
    if line_filter is not None:
        raise ValueError("unsupported capture line selection")
    if provenance and provenance.get("assessment"):
        from .related_capture_objective import apply

        apply(snapshot, provenance["assessment"])


def _other(snapshot, provenance, provenance_key, line_filter):
    if provenance_key in {
        "related_fork",
        "related_protection",
        "related_fork_prevention",
        "related_fork_avoidance",
        "related_mate",
        "related_pin",
        "related_backrank_attack",
    }:
        version = {
            "related_protection": PROTECTION_FILTER,
            "related_fork_prevention": related_fork_prevention_contract.FILTER_VERSION,
            "related_fork_avoidance": related_fork_avoidance_contract.FILTER_VERSION,
            "related_mate": related_mate.FILTER_VERSION,
            "related_pin": related_pin_contract.FILTER_VERSION,
            "related_backrank_attack": related_backrank_contract.FILTER_VERSION,
        }.get(provenance_key)
        select_lines(snapshot, provenance, expected_version=version)
        if snapshot["lines"] != line_filter:
            raise ValueError("practice line selection unavailable")
        apply_fork(snapshot, provenance, provenance_key)
        if provenance_key == "related_pin":
            snapshot["objective"] = "legal_line"
        if provenance_key in {"related_mate", "related_backrank_attack"}:
            snapshot["objective"] = "checkmate"
        if provenance_key == "related_mate" and provenance.get("assessment"):
            snapshot["objective"] = "mate_within_two"
            snapshot["lines"] = provenance["assessment"]["lines"]
    elif line_filter is not None:
        raise ValueError("unsupported practice line selection")
