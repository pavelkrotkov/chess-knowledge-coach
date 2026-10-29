"""Reject changed or revoked own-game evidence for existing sessions."""

import hashlib
import json

from .unified_sources import resolve_source


def snapshot_hash(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def require_current(db, row):
    if row["source_type"] != "own-game":
        return
    try:
        snapshot = resolve_source(
            db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
        )
        if snapshot_hash(snapshot) != row["snapshot_hash"]:
            raise ValueError
    except ValueError:
        raise ValueError("practice source unavailable or stale") from None
