"""Recognize independently validated material families and versions."""

from .material_contract import PRODUCER as MATERIAL_PRODUCER
from .material_policy import ELIGIBLE_KINDS, OPERATIONS


def material_ok(row, fact):
    payload = fact["payload"]
    return (
        fact["producer"] == MATERIAL_PRODUCER
        and fact["fact_type"] == "material_opportunity"
        and fact["detector_version"] == fact["run_detector_version"]
        and (payload.get("kind"), fact["detector_version"]) in ELIGIBLE_KINDS
        and row["skill"] == "hanging_piece"
        and row["operation"] == OPERATIONS.get(payload.get("kind"))
    )
