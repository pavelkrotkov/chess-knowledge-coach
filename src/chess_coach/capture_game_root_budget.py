"""Bound optional root detail in the existing atomic report."""

from .fact_fingerprint import canonical, digest
from .short_mate_trend_store import MAX_BYTES

DETAIL_BYTES = 256 * 1024
DETAIL_TURNS = 2048


def _items(state):
    yield from state.get("games", [])
    yield from state.get("retained", {}).values()
    prior = state.get("prior")
    if prior:
        yield from prior.get("games", [])
        yield from prior.get("retained", {}).values()


def room(state, item, section):
    sections = [
        value["root_details"]
        for value in _items(state)
        if value is not item and value.get("root_details")
    ]
    sections.append(section)
    return (
        sum(len(value["turns"]) for value in sections) <= DETAIL_TURNS
        and sum(len(canonical({"root_details": value}).encode()) for value in sections)
        <= DETAIL_BYTES
    )


def fit(state):
    body = canonical(state)
    encoded = canonical({**state, "checksum": digest(body)}).encode()
    if len(encoded) <= MAX_BYTES:
        return
    for item in _items(state):
        item.pop("root_details", None)
