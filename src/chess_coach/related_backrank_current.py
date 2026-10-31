"""Recheck source and selected supplied line for every resumed transfer."""

import json

from . import related_backrank_contract as contract
from .recurrence_snapshot import read_snapshot
from .related_backrank_source import source_for_evidence
from .related_fork_lines import select_lines
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_backrank_attack")
    if binding is None:
        return
    try:
        with read_snapshot(db):
            _recheck(db, row, snapshot_hash, binding)
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None


def _recheck(db, row, snapshot_hash, binding):
    source = source_for_evidence(db, row["subject"], binding["evidence_id"], binding["root_move"])
    if snapshot_hash(source) != binding["source_snapshot_hash"]:
        raise ValueError
    if (
        binding["rank_version"],
        binding["motif"],
        binding["operation"],
        binding["mate_timing"],
    ) != (contract.VERSION, "backrank_attack", "execute", source["objective"]):
        raise ValueError
    candidate = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(candidate, binding, expected_version=contract.FILTER_VERSION)
    candidate["objective"] = "checkmate"
    candidate["provenance"]["related_backrank_attack"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"]:
        raise ValueError
