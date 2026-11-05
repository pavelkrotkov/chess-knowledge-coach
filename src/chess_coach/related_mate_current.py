"""Recheck the owned mate source and selected public line on every resume."""

import json

from . import related_mate
from .related_fork_lines import select_lines
from .related_mate_search_token import VERSION as SEARCH_VERSION
from .related_mate_source import source_for_evidence
from .unified_sources import resolve_source


def require_current(db, row, snapshot_hash):
    binding = json.loads(row["provenance_json"]).get("related_mate")
    if binding is None:
        return
    try:
        source = source_for_evidence(db, row["subject"], binding["evidence_id"])
        if snapshot_hash(source) != binding["source_snapshot_hash"]:
            raise ValueError
        if binding["rank_version"] not in {related_mate.VERSION, SEARCH_VERSION}:
            raise ValueError
        if (binding["motif"], binding["operation"], binding["mate_timing"]) != (
            "mate",
            "execute",
            source["objective"],
        ):
            raise ValueError
        candidate = resolve_source(
            db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
        )
        select_lines(candidate, binding, expected_version=related_mate.FILTER_VERSION)
        candidate["objective"] = "checkmate"
        if binding.get("assessment"):
            from .related_mate_assessment_current import validate

            validate(db, row, binding, candidate)
            candidate["objective"] = "mate_within_two"
            candidate["lines"] = binding["assessment"]["lines"]
        candidate["provenance"]["related_mate"] = binding
        if snapshot_hash(candidate) != row["snapshot_hash"]:
            raise ValueError
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("practice source unavailable or stale") from None
