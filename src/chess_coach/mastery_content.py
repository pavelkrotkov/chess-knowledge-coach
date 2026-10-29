"""Validate reviewed evidence content and detector-family eligibility."""

from .mastery_family_reasons import family_exclusion as _family_reason
from .mastery_provenance import valid_confidence, valid_links
from .material_mastery_source import source_reason


def content_reason(db, row) -> str | None:
    reason = _family_reason(db, row)
    if reason:
        return reason
    if row["outcome"] not in {"success", "failure"}:
        return "ambiguous"
    if not valid_confidence(row["confidence"]):
        return "invalid_confidence"
    if not valid_links(row):
        return "unproven_source"
    return None


def final_reason(db, row):
    reason = content_reason(db, row)
    return reason if reason else source_reason(db, row)
