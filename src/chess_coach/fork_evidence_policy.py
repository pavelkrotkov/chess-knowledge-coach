"""Require a matching provisional fork mapping and linked source fact."""

from .fork_contract import PRODUCER, VERSION


def valid_fact(evidence, fact):
    payload = fact.get("payload")
    return (
        _mapping(evidence)
        and _source(fact)
        and (
            isinstance(payload, dict)
            and payload.get("kind") == "fork"
            and payload.get("outcome") == evidence["outcome"]
        )
    )


def _mapping(evidence):
    return (
        evidence["lifecycle_status"] == "active"
        and evidence["skill"] == "fork"
        and evidence["operation"] == "execute"
    )


def _source(fact):
    return (
        fact["producer"] == PRODUCER
        and fact["fact_type"] == "fork_opportunity"
        and fact["detector_status"] == "active"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
    )
