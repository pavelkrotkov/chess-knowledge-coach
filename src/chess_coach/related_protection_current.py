"""Invalidate protection practice when its source or supplied lines change."""

import json

from .related_fork_lines import select_lines
from .related_protection_contract import FILTER_VERSION
from .related_protection_source import source_for_evidence
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_protection")
    if binding is None:
        return
    try:
        source = source_for_evidence(db, row["subject"], binding["evidence_id"])
        if snapshot_hash(source) != binding["source_snapshot_hash"]:
            raise ValueError
        candidate = resolve_source(
            db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
        )
        select_lines(candidate, binding, expected_version=FILTER_VERSION)
        candidate["provenance"]["related_protection"] = binding
        if snapshot_hash(candidate) != row["snapshot_hash"]:
            raise ValueError
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None
