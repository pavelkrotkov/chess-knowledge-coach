"""Check review, mapping, and linked-source eligibility."""

from .mastery_content import final_reason
from .mastery_provenance import is_pending_training, training_reason


def basic_reason(db, row, subject: str) -> str | None:
    if not subject or subject in {"default", "unassigned", "?", "-"}:
        return "unassigned_subject"
    if row["review_decision"] != "accept" or row["human_validated"] != 1:
        return _review_reason(row)
    if is_pending_training(row):
        return training_reason(row)
    if row["mapping_run_id"] is None or row["mapping_status"] != "active":
        return "superseded_or_unscoped"
    return final_reason(db, row)


def _review_reason(row) -> str:
    if row["review_decision"] in {"reject", "revoke"}:
        return {"reject": "rejected", "revoke": "revoked"}[row["review_decision"]]
    if row["human_validated"] == 1 and row["review_decision"] is None:
        return "legacy_review"
    return "unreviewed_or_invalid_review"
