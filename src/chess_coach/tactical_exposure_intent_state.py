"""Interpret the owner-bound tactical Study chapter ledger."""

from .tactical_exposure_intent_entry import entry_status
from .tactical_exposure_intent_progress import uncovered
from .tactical_study_exposure import VERSION


def _chapters(delivery):
    chapters = delivery.get("chapters")
    if not isinstance(chapters, dict) or len(chapters) > 63:
        raise ValueError("tactical Study exposure unavailable")
    return chapters


def _delivery(state, owner):
    delivery = state.get("tactical_delivery")
    if not isinstance(delivery, dict) or delivery.get("version") != VERSION:
        return None
    identity = delivery.get("owner")
    if not isinstance(identity, str) or len(identity) != 64:
        raise ValueError("tactical Study exposure owner unavailable")
    return _chapters(delivery) if identity == owner else False


def tracked(state, owner, target, cutoff):
    chapters = _delivery(state, owner)
    if chapters is None:
        return None
    if chapters is False:
        return "not_recorded"
    # Each stored chapter retains its own possible-send interval.
    states = [entry_status(entry, target, cutoff) for entry in chapters.values()]
    if "provided" in states:
        return "provided"
    if uncovered(state, chapters) or "publication_time_unknown" in states:
        return "publication_time_unknown"
    return "not_recorded"
