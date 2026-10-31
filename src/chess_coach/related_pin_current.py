"""Recheck the owned pin source and selected external lines on resume."""

import json

from . import related_pin_contract as contract
from .recurrence_snapshot import read_snapshot
from .related_fork_lines import select_lines
from .related_pin_source import source_for_evidence
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_pin")
    if binding is None:
        return
    try:
        with read_snapshot(db):
            _recheck(db, row, snapshot_hash, binding)
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None


def _recheck(db, row, snapshot_hash, binding):
    source = source_for_evidence(db, row["subject"], binding["evidence_id"])
    if snapshot_hash(source) != binding["source_snapshot_hash"]:
        raise ValueError
    if (binding["rank_version"], binding["motif"], binding["operation"]) != (
        contract.VERSION,
        "pin",
        "execute",
    ):
        raise ValueError
    candidate = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(candidate, binding, expected_version=contract.FILTER_VERSION)
    candidate["objective"] = "legal_line"
    candidate["provenance"]["related_pin"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"]:
        raise ValueError
