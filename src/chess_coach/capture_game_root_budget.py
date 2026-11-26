"""Bound optional root detail in the existing atomic report."""

from itertools import chain

from .capture_game_proof import VERSION as PROOF_VERSION
from .fact_fingerprint import canonical
from .short_mate_trend_store import MAX_BYTES

VERSION = "capture-game-roots-v1"
DETAIL_BYTES = 256 * 1024
DETAIL_TURNS = 2048


def _items(state):
    prior = state.get("prior") or {}
    return chain(
        state.get("games", ()),
        state.get("retained", {}).values(),
        prior.get("games", ()),
        prior.get("retained", {}).values(),
    )


def _limits(sections):
    return (
        sum(len(value["turns"]) for value in sections) <= DETAIL_TURNS
        and sum(len(canonical({"root_details": value}).encode()) for value in sections)
        <= DETAIL_BYTES
    )


def fits(state):
    return len(canonical({**state, "checksum": "0" * 64}).encode()) <= MAX_BYTES


def fit(state):
    items = list(_items(state))
    pending = [item for item in items if item.get("root_details")]
    while pending and (
        not _limits([item["root_details"] for item in items if item.get("root_details")])
        or not fits(state)
    ):
        pending.pop().pop("root_details", None)


def record(state, item, row, detail):
    section = item.get("root_details") or {"version": VERSION, "proof": PROOF_VERSION, "turns": []}
    value = {**detail, "position_id": row[0], "outcome": row[1], "reason": row[2]}
    item["root_details"] = {**section, "turns": [*section["turns"], value]}
    fit(state)
