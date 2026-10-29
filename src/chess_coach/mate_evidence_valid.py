"""Validate source lineage for a mate observation."""

from .mate_contract import PRODUCER, VERSION
from .material_opportunity_links import valid_link


def valid(db, evidence, fact):
    return (
        evidence["lifecycle_status"] == "active"
        and fact["detector_status"] == "active"
        and fact["producer"] == PRODUCER
        and fact["fact_type"] == "bounded_mate"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
        and evidence["mapper_version"] == VERSION
        and isinstance(fact["payload"], dict)
        and valid_link(db, evidence, fact)
    )
