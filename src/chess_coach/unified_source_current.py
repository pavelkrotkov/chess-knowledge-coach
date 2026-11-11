"""Reject changed or revoked own-game evidence for existing sessions."""

import hashlib
import json

from .objective_fork_defense_budget import BudgetExceeded
from .objective_pin_prevent_budget import BudgetExceeded as PinBudgetExceeded
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .unified_sources import resolve_source


def snapshot_hash(snapshot):
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def require_current(db, row, *, related_cache=None, related_check=None):
    _require_related_current(db, row, related_cache, related_check)
    from .related_transfer_current import require_current as require_transfers_current

    require_transfers_current(
        db, row, snapshot_hash, fork_check=related_check, fork_cache=related_cache
    )
    public = row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES
    if row["source_type"] != "own-game" and not public:
        return
    try:
        snapshot = resolve_source(
            db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
        )
        if snapshot_hash(snapshot) != row["snapshot_hash"]:
            raise ValueError
    except (BudgetExceeded, PinBudgetExceeded):
        raise
    except ValueError:
        raise ValueError("practice source unavailable or stale") from None


def _related_source(db, row, binding, cache, check):
    from .related_capture_source import source_for_position

    key = (row["subject"], binding["position_id"])
    if cache is not None and key in cache:
        return cache[key]
    source = (
        source_for_position(db, *key, check=check)
        if check is not None
        else source_for_position(db, *key)
    )
    if cache is not None:
        cache[key] = source
    return source


def _require_related_current(db, row, cache=None, check=None):
    binding = json.loads(row["provenance_json"]).get("related_capture")
    if binding is None:
        return
    try:
        source = _related_source(db, row, binding, cache, check)
        if snapshot_hash(source) != binding["source_snapshot_hash"]:
            raise ValueError
        # A corpus assessment additionally binds its reset setup and certificate.
        if binding.get("assessment"):
            from .related_capture_objective import current

            current(db, row, binding, snapshot_hash)
    except (ValueError, TypeError, KeyError):
        raise ValueError("practice source unavailable or stale") from None
