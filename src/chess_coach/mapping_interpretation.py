"""Validate the interpretation stored for one mapping."""

import math


def validate_interpretation(item: dict) -> None:
    if not isinstance(item["skill"], str) or not item["skill"].strip():
        raise ValueError("skill must be nonempty")
    if item["outcome"] not in {"success", "failure", "ambiguous"}:
        raise ValueError("invalid mapping outcome")
    confidence = item["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("invalid mapping confidence")
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("invalid mapping confidence")
