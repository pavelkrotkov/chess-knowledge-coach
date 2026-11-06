"""Identify source-scoped sessions with verification status."""

from .objective_binding_scope import owned_source
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .related_capture_objective import is_source as capture_assessment


def enabled(row):
    public = row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES
    return (public or capture_assessment(row) or owned_source(row)) and row[
        "status"
    ] == "needs_verification"
