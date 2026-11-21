"""Validate and classify one tactical Study chapter's send interval."""

from .tactical_exposure_intent_time import times


def _positions(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("positions"), list):
        raise ValueError("tactical Study exposure unavailable")
    values = entry["positions"]
    if not values or len(values) > 4096:
        raise ValueError("tactical Study exposure unavailable")
    if any(not isinstance(value, str) or len(value) != 64 for value in values):
        raise ValueError("tactical Study exposure unavailable")
    return values


def entry_status(entry, target, cutoff):
    positions = _positions(entry)
    sent, verified = times(entry)
    if target not in positions:
        return "not_recorded"
    if verified is not None and verified <= cutoff:
        return "provided"
    if sent is None or sent <= cutoff:
        return "publication_time_unknown"
    return "not_recorded"
