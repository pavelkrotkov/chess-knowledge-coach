"""Recheck a discovered-mate source, candidate and first encounter."""

import json

from .related_created_novel import require_created_novel
from .related_discovery_contract import KEY, is_source, recheck
from .related_discovery_source import source_for_evidence


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get(KEY)
    if binding is None:
        return
    try:
        generation = db.connection.execute("PRAGMA data_version").fetchone()[0]
        _recheck(db, row, binding, snapshot_hash)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != generation:
            raise ValueError("discovered mate source changed")
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None


def _recheck(db, row, binding, snapshot_hash):
    if not is_source(row):
        raise ValueError("discovered mate binding changed")
    source = source_for_evidence(db, row["subject"], binding["evidence_id"])
    if snapshot_hash(source) != binding["source_snapshot_hash"]:
        raise ValueError("discovered mate source changed")
    recheck(db, row, binding, source, snapshot_hash)
    if row["status"] == "active" and row["next_index"] == 0:
        require_created_novel(db, row, binding, binding.get("source_game"))
