"""Reconstruct and verify a pin fact against its current owned source."""

from functools import partial

from .fork_evidence_current import current_fork
from .fork_evidence_verify import verified_fen
from .pin_defense import observe as defense
from .pin_evidence_identity import mapper_current
from .pin_observation import observe as execute
from .pin_pipeline import VERSION, _names


def current_pin(db, evidence, operation, *, _history=None):
    _, mapper, _ = _names(operation)
    if evidence["mapping_producer"] == mapper and not mapper_current(db, evidence):
        return {}, "stale", None
    observer = execute if operation == "execute" else defense
    return current_fork(
        db,
        evidence,
        mapper=mapper,
        validator=partial(_valid, operation=operation),
        verify=partial(verified_fen, observer=observer),
        _history=_history,
    )


def _valid(evidence, fact, *, operation):
    producer, _, fact_type = _names(operation)
    payload = fact.get("payload")
    return _mapping(evidence, payload, operation) and _source(fact, producer, fact_type)


def _mapping(evidence, payload, operation):
    return (
        evidence["lifecycle_status"] == "active"
        and evidence["operation"] == operation
        and isinstance(payload, dict)
        and evidence["skill"] == payload.get("kind")
        and payload.get("kind") in {"absolute_pin", "relative_pin"}
        and payload.get("outcome") == evidence["outcome"]
    )


def _source(fact, producer, fact_type):
    return (
        fact["producer"] == producer
        and fact["fact_type"] == fact_type
        and fact["detector_status"] == "active"
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
    )
