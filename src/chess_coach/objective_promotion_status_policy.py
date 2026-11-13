"""Identify source-scoped sessions with verification status."""

from .objective_binding_scope import owned_source
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .related_capture_objective import is_source as capture_assessment
from .related_created_objective import is_source as created_assessment
from .related_fork_assessment_scope import is_source as fork_assessment
from .related_protection_objective import is_source as protection_assessment


def enabled(row):
    public = row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES
    return (
        public
        or capture_assessment(row)
        or created_assessment(row)
        or fork_assessment(row)
        or protection_assessment(row)
        or owned_source(row)
    ) and row["status"] == "needs_verification"
