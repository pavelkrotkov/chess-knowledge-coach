"""Reject changed or revoked own-game evidence for existing sessions."""

import hashlib
import json

from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .unified_sources import resolve_source


def snapshot_hash(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def require_current(db, row):
    _require_related_current(db, row)
    from .related_fork_current import require_current as require_fork_current

    require_fork_current(db, row, snapshot_hash)
    public = row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES
    if row["source_type"] != "own-game" and not public:
        return
    try:
        snapshot = resolve_source(
            db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
        )
        if snapshot_hash(snapshot) != row["snapshot_hash"]:
            raise ValueError
    except ValueError:
        raise ValueError("practice source unavailable or stale") from None


def _require_related_current(db, row):
    binding = json.loads(row["provenance_json"]).get("related_capture")
    if binding is None:
        return
    from .related_capture_source import source_for_position

    try:
        source = source_for_position(db, row["subject"], binding["position_id"])
        if snapshot_hash(source) != binding["source_snapshot_hash"]:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError("practice source unavailable or stale") from None
