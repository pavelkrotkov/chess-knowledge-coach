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


def _limits(items):
    items = list(items)
    turns = sum(len(item["root_details"]["turns"]) for item in items if item.get("root_details"))
    size = sum(
        len(canonical({key: item[key]}).encode())
        for item in items
        for key in ("root_details", "root_refresh")
        if item.get(key)
    )
    return turns <= DETAIL_TURNS and size <= DETAIL_BYTES


def fits(state):
    return _limits(_items(state)) and (
        len(canonical({**state, "checksum": "0" * 64}).encode()) <= MAX_BYTES
    )


def fit(state):
    for item in reversed(list(_items(state))):
        if fits(state):
            break
        item.pop("root_details", None)


def record(state, item, row, detail, *, version=VERSION, proof=PROOF_VERSION):
    section = item.get("root_details") or {"version": version, "proof": proof, "turns": []}
    value = {**detail, "position_id": row[0], "outcome": row[1], "reason": row[2]}
    item["root_details"] = {**section, "turns": [*section["turns"], value]}
    fit(state)
