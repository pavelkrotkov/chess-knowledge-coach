"""Check review, mapping, and linked-source eligibility."""

from .mastery_provenance import is_pending_training, training_reason, valid_confidence, valid_links


def basic_reason(row, subject: str) -> str | None:
    if not subject or subject in {"default", "unassigned", "?", "-"}:
        return "unassigned_subject"
    if row["review_decision"] != "accept" or row["human_validated"] != 1:
        return _review_reason(row)
    if is_pending_training(row):
        return training_reason(row)
    if row["mapping_run_id"] is None or row["mapping_status"] != "active":
        return "superseded_or_unscoped"
    return _content_reason(row)


def _review_reason(row) -> str:
    if row["review_decision"] in {"reject", "revoke"}:
        return {"reject": "rejected", "revoke": "revoked"}[row["review_decision"]]
    if row["human_validated"] == 1 and row["review_decision"] is None:
        return "legacy_review"
    return "unreviewed_or_invalid_review"


def _content_reason(row) -> str | None:
    if row["outcome"] not in {"success", "failure"}:
        return "ambiguous"
    if not valid_confidence(row["confidence"]):
        return "invalid_confidence"
    if not valid_links(row):
        return "unproven_source"
    return None
