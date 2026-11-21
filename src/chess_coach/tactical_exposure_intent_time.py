"""Validate publication time bounds for a tactical Study chapter."""

from .mastery_time import parse_utc


def times(entry):
    result = []
    for field in ("pending_at", "verified_at"):
        raw = entry.get(field)
        parsed = parse_utc(raw)
        if raw is not None and parsed is None:
            raise ValueError("tactical Study exposure time unavailable")
        result.append(parsed)
    if not any(result):
        raise ValueError("tactical Study exposure time unavailable")
    sent, verified = result
    if sent is not None and verified is not None and verified < sent:
        raise ValueError("tactical Study exposure time unavailable")
    return sent, verified
