"""Recheck discovery evidence against the current owned decision."""

from functools import partial

from .discovery_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION
from .discovery_observation import observe
from .fork_evidence_current import current_fork
from .fork_evidence_verify import verified_fen


def _valid(evidence, fact):
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


def current(db, evidence):
    verify = partial(verified_fen, observer=observe)
    return current_fork(db, evidence, mapper=MAPPER, validator=_valid, verify=verify)
