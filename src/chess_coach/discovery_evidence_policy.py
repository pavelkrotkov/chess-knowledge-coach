"""Validate the discovery mapping and detector fact contract."""

from .discovery_contract import FACT, PRODUCER, SCOPE, VERSION


def valid(evidence, fact):
    payload = fact.get("payload")
    return (
        _mapping(evidence)
        and _source(fact)
        and isinstance(payload, dict)
        and (payload.get("kind"), payload.get("outcome"))
        == ("discovered_attack", evidence["outcome"])
    )


def _mapping(evidence):
    return (
        evidence["lifecycle_status"] == "active"
        and evidence["skill"] == "discovered_attack"
        and evidence["operation"] == "execute"
        and evidence["mapper_version"] == VERSION
        and evidence["mapping_scope"] == SCOPE
    )


def _source(fact):
    return (
        fact["producer"] == PRODUCER
        and fact["fact_type"] == FACT
        and fact["detector_status"] == "active"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
    )
