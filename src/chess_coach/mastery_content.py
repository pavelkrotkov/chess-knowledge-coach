"""Validate reviewed evidence content and detector-family eligibility."""

from .mastery_provenance import valid_confidence, valid_links
from .material_mastery_source import source_reason
from .material_policy import mastery_allowed


def content_reason(row) -> str | None:
    if not mastery_allowed(row):
        return "material_family_unvalidated"
    if row["outcome"] not in {"success", "failure"}:
        return "ambiguous"
    if not valid_confidence(row["confidence"]):
        return "invalid_confidence"
    if not valid_links(row):
        return "unproven_source"
    return None


def final_reason(db, row):
    reason = content_reason(row)
    return reason if reason else source_reason(db, row)
