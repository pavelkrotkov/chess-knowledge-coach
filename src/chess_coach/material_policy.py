"""Independently approved, exact material kind and detector-version pairs."""

from .material_contract import PRODUCER

MAPPER = "material-opportunity-mapper"
ELIGIBLE_KINDS = frozenset({("material_protection", "1.0.0"), ("material_capture", "1.1.0")})
OPERATIONS = {"material_protection": "prevent", "material_capture": "execute"}


def fact_allowed(fact, *, skill, operation, outcome):
    if not _source_allowed(fact):
        return False
    payload = fact["payload"]
    return (
        skill == "hanging_piece"
        and operation == OPERATIONS.get(payload["kind"])
        and outcome in {"success", "failure"}
        and payload.get("outcome") == outcome
    )


def _source_allowed(fact):
    payload = fact.get("payload")
    if not isinstance(payload, dict):
        return False
    kind, version = payload.get("kind"), fact.get("detector_version")
    if not isinstance(kind, str) or not isinstance(version, str):
        return False
    return (
        fact.get("producer") == PRODUCER
        and fact.get("fact_type") == "material_opportunity"
        and version == fact.get("run_detector_version")
        and (kind, version) in ELIGIBLE_KINDS
    )
