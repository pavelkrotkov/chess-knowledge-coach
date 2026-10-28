"""Check numeric confidence and active linked fact provenance."""

import math


def valid_confidence(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= 1
    )


def valid_links(row) -> bool:
    return (
        row["source_provenance"] == "linked"
        and row["link_count"] > 0
        and row["invalid_links"] == 0
        and row["mapping_subject"] == row["subject"]
        and row["mapping_operation"] == row["operation"]
        and row["mapping_position"] == row["position_id"]
        and isinstance(row["review_actor"], str)
        and bool(row["review_actor"].strip())
    )


def is_pending_training(row) -> bool:
    return row["position_id"] is None and row["source_provenance"] == "training_attempt"
