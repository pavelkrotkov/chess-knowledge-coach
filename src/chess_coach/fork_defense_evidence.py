"""Check a linked fork-defense fact against its exact owned current source."""

from .fork_defense_contract import FACT_TYPE, MAPPER, PRODUCER, VERSION
from .fork_defense_observation import observe
from .fork_evidence_current import current_fork
from .fork_evidence_verify import verified_fen


def current_defense(db, evidence, *, _history=None):
    return current_fork(
        db, evidence, mapper=MAPPER, validator=_valid, verify=_verify, _history=_history
    )


def _verify(db, evidence, fact, *, _history=None):
    return verified_fen(db, evidence, fact, observer=observe, _history=_history)


def _valid(evidence, fact):
    payload = fact.get("payload")
    return (
        _mapping(evidence)
        and _source(fact)
        and (
            isinstance(payload, dict)
            and payload.get("kind") == "fork_defense"
            and payload.get("outcome") == evidence["outcome"]
        )
    )


def _mapping(evidence):
    return (
        evidence["lifecycle_status"] == "active"
        and evidence["skill"] == "fork"
        and evidence["operation"] == "prevent"
    )


def _source(fact):
    return (
        fact["producer"] == PRODUCER
        and fact["fact_type"] == FACT_TYPE
        and fact["detector_status"] == "active"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
    )
