"""Validate and fingerprint a complete evidence-mapping batch."""

from .fact_fingerprint import canonical, digest
from .mapping_item import prepare_mapping


def mapping_batch(mappings: list[dict]) -> tuple[list[dict], str]:
    if not isinstance(mappings, list):
        raise ValueError("mappings must be a list")
    prepared = [prepare_mapping(item) for item in mappings]
    prepared.sort(key=canonical)
    keys = [(item["skill"], fact_id) for item in prepared for fact_id in item["fact_ids"]]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate effective fact mapping")
    return prepared, digest(canonical(prepared))
