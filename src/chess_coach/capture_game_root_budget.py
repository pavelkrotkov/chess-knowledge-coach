"""Bound optional root detail in the existing atomic report."""

from .fact_fingerprint import canonical
from .short_mate_trend_store import MAX_BYTES

VERSION = "capture-game-roots-v1"
DETAIL_BYTES = 256 * 1024
DETAIL_TURNS = 2048


def _items(state):
    yield from state.get("games", [])
    yield from state.get("retained", {}).values()
    prior = state.get("prior")
    if prior:
        yield from prior.get("games", [])
        yield from prior.get("retained", {}).values()


def _limits(sections):
    return (
        sum(len(value["turns"]) for value in sections) <= DETAIL_TURNS
        and sum(len(canonical({"root_details": value}).encode()) for value in sections)
        <= DETAIL_BYTES
    )


def room(state, item, section):
    sections = [section if value is item else value.get("root_details") for value in _items(state)]
    return _limits([value for value in sections if value])


def fits(state):
    return len(canonical({**state, "checksum": "0" * 64}).encode()) <= MAX_BYTES


def _trim(state, items):
    pending = [item for item in items if item.get("root_details")]
    while pending and (
        not _limits([item["root_details"] for item in items if item.get("root_details")])
        or not fits(state)
    ):
        item = pending.pop()
        item["root_details"] = {**item["root_details"], "turns": []}


def fit(state):
    items = list(_items(state))
    _trim(state, items)
    if not fits(state):
        for item in items:
            item.pop("root_details", None)
