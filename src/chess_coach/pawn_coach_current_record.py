"""Validate pawn evidence identity, versions and linked detector lineage."""

from .material_opportunity_links import valid_link
from .pawn_coach_contract import FACT_TYPE, PRODUCER, SKILL, VERSION


def valid_record(db, evidence):
    if evidence["lifecycle_status"] != "active" or evidence["skill"] != SKILL:
        return False
    if evidence["source_provenance"] != "linked":
        return False
    if evidence["mapper_version"] != VERSION or len(evidence["facts"]) != 1:
        return False
    fact = evidence["facts"][0]
    if not valid_link(db, evidence, fact):
        return False
    return _fact_valid(fact)


def _fact_valid(fact):
    return (
        fact["producer"] == PRODUCER
        and fact["fact_type"] == FACT_TYPE
        and fact["detector_status"] == "active"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
    )
