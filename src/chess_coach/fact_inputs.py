"""Canonical identities for detector inputs and fact batches."""

from __future__ import annotations

from typing import Any

from .fact_fingerprint import canonical, digest


def fact_batch(facts: list[dict[str, Any]]) -> tuple[list[tuple[str, str, str]], str]:
    if not isinstance(facts, list):
        raise ValueError("facts must be a list")
    result = []
    for fact in facts:
        result.append(prepare_fact(fact))
    result.sort()
    keys = [item[0] for item in result]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate fact in detector output")
    return result, digest(canonical(keys))


def prepare_fact(fact: dict[str, Any]) -> tuple[str, str, str]:
    if not isinstance(fact, dict) or set(fact) != {"fact_type", "payload"}:
        raise ValueError("each fact requires fact_type and payload")
    fact_type = fact["fact_type"]
    if not isinstance(fact_type, str) or not fact_type.strip():
        raise ValueError("fact_type must be a nonempty string")
    if not isinstance(fact["payload"], dict):
        raise ValueError("fact payload must be an object")
    payload = canonical(fact["payload"])
    key = digest(canonical({"fact_type": fact_type, "payload": fact["payload"]}))
    return key, fact_type, payload
