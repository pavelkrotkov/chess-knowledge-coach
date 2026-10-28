"""Validate individual evidence mappings."""

from .fact_fingerprint import canonical
from .mapping_interpretation import validate_interpretation


def prepare_mapping(item: dict) -> dict:
    fields = {"skill", "outcome", "confidence", "fact_ids", "context", "observation_at"}
    if not isinstance(item, dict) or set(item) != fields:
        raise ValueError(
            "mapping requires skill, outcome, confidence, fact_ids, context, observation_at"
        )
    validate_interpretation(item)
    _validate_source_and_context(item)
    result = {**item, "fact_ids": sorted(item["fact_ids"])}
    canonical(result)
    return result


def _validate_source_and_context(item: dict) -> None:
    _validate_ids(item["fact_ids"])
    if not isinstance(item["context"], dict):
        raise ValueError("mapping context must be an object")
    if item["observation_at"] is not None and not isinstance(item["observation_at"], str):
        raise ValueError("observation time must be a string or unknown")


def _validate_ids(ids) -> None:
    if not isinstance(ids, list) or not ids or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError("mapping requires source fact ids")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate source fact id")
