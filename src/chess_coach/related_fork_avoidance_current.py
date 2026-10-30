"""Recheck the original created-fork source and the candidate on every resume."""

import json

from . import related_fork_avoidance_contract as contract
from .recurrence_snapshot import read_snapshot
from .related_fork_avoidance_source import source_for_evidence
from .related_fork_lines import select_lines
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_fork_avoidance")
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
    if (
        binding["rank_version"],
        binding["motif"],
        binding["operation"],
        binding["threat_origin"],
    ) != (contract.VERSION, "fork_avoidance", "prevent", "created_by_played_move"):
        raise ValueError
    candidate = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(candidate, binding, expected_version=contract.FILTER_VERSION)
    candidate["provenance"]["related_fork_avoidance"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"]:
        raise ValueError
