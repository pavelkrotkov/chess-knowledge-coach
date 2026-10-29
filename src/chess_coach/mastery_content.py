"""Validate reviewed evidence content and detector-family eligibility."""

from .fork_family_policy import closed_reason
from .fork_mastery_policy import mastery_allowed as fork_mastery_allowed
from .mastery_provenance import valid_confidence, valid_links
from .material_mastery_policy import mastery_allowed
from .material_mastery_source import source_reason


def content_reason(db, row) -> str | None:
    reason = closed_reason(row)
    if reason:
        return reason
    if not fork_mastery_allowed(db, row):
        return "fork_family_unvalidated"
    if not mastery_allowed(db, row):
        return "material_family_unvalidated"
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
