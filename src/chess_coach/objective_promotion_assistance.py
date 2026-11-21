"""Identify objective sessions whose assistance is tracked."""

from .objective_assistance_policy import objective_assistance
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .public_training_source import mate as public_mate
from .related_pin_assistance import assistance as pin_assistance


def assistance(row):
    return (
        objective_assistance(row)
        or pin_assistance(row)
        or public_mate(row)
        or (row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES)
    )
