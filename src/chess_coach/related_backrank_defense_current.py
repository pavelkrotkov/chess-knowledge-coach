"""Recheck the owned source and exact corpus defense on session use."""

import json

from .recurrence_snapshot import read_snapshot
from .related_backrank_contract import defense_filter, defense_version
from .related_backrank_defense_proof import proof
from .related_backrank_defense_source import source_for_evidence
from .related_capture_assessment import setup
from .related_fork_lines import select_lines
from .unified_sources import resolve_source


def _recheck(db, row, snapshot_hash, binding):
    source = source_for_evidence(db, row["subject"], binding["evidence_id"])
    if snapshot_hash(source) != binding["source_snapshot_hash"]:
        raise ValueError("back-rank source changed")
    version = defense_version(source)
    if (binding["rank_version"], binding["motif"], binding["operation"], row["source_type"]) != (
        version,
        "backrank_defense",
        "prevent",
        "corpus",
    ):
        raise ValueError("back-rank binding changed")
    candidate = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(candidate, binding, expected_version=defense_filter(version))
    board, _, _ = setup(db, row["source_version"], row["source_key"])
    if board.fen() != candidate["prompt_fen"]:
        raise ValueError("back-rank prompt changed")
    move = board.parse_uci(candidate["lines"][0].split()[0])
    if proof(board, move, source) != binding["defense_witness"]:
        raise ValueError("back-rank proof changed")
    candidate["objective"] = "legal_line"
    candidate["provenance"]["related_backrank_defense"] = binding
    if snapshot_hash(candidate) != row["snapshot_hash"]:
        raise ValueError("back-rank snapshot changed")


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_backrank_defense")
    if binding is None:
        return
    try:
        with read_snapshot(db):
            _recheck(db, row, snapshot_hash, binding)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise ValueError("practice source unavailable or stale") from None
