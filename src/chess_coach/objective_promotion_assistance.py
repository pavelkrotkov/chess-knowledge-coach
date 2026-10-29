"""Identify objective sessions whose assistance is tracked."""

from .objective_assistance_policy import objective_assistance
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES


def assistance(row):
    return objective_assistance(row) or (
        row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES
    )
