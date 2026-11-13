"""Recheck the bound source, candidate and novelty for created-exposure practice."""

import json

from .related_created_candidate import recheck as recheck_candidate
from .related_created_contract import FILTER_VERSION, KEY, VERSION
from .related_created_novel import require_created_novel
from .related_created_source import source_for_evidence
from .related_fork_lines import select_lines
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get(KEY)
    if binding is None:
        return
    try:
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        _recheck(db, row, binding, snapshot_hash)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("practice source changed")
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None


def _recheck(db, row, binding, snapshot_hash):
    source = source_for_evidence(db, row["subject"], binding["evidence_id"])
    if snapshot_hash(source) != binding["source_snapshot_hash"]:
        raise ValueError("created exposure source changed")
    if (binding["rank_version"], binding["motif"], binding["operation"]) != (
        VERSION,
        "created_exposure",
        "prevent",
    ):
        raise ValueError("created exposure binding changed")
    selected = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(selected, binding, expected_version=FILTER_VERSION)
    recheck_candidate(db, row, selected, binding, source)
    selected["objective"] = "legal_line"
    selected["provenance"][KEY] = binding
    if snapshot_hash(selected) != row["snapshot_hash"]:
        raise ValueError("practice snapshot changed")
    if row["status"] == "active" and row["next_index"] == 0:
        require_created_novel(db, row, binding)
