"""Recheck original evidence and supplied-line identity for active practice."""

import json

from . import related_fork_prevention_contract
from .recurrence_snapshot import read_snapshot
from .related_fork_lines import select_lines
from .related_fork_prevention_source import source_for_evidence
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_fork_prevention")
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
    candidate = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(
        candidate, binding, expected_version=related_fork_prevention_contract.FILTER_VERSION
    )
    candidate["provenance"]["related_fork_prevention"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"]:
        raise ValueError
