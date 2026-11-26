"""Validate optional root-section provenance before worker resume."""

from .capture_game_proof import VERSION as PROOF_VERSION
from .capture_game_root_budget import VERSION, _items, _limits, fits, room


def _section(item):
    section = item.get("root_details")
    if section is None:
        return True
    try:
        turns, cursor = section["turns"], section.get("next", 0)
        rows = {(row[0], row[1]) for row in item["results"]}
        retained = [(turn["position_id"], turn["outcome"]) for turn in turns]
        tag = (section["version"], section["proof"], type(cursor), type(turns))
        return (
            tag == (VERSION, PROOF_VERSION, int, list)
            and cursor in range(len(rows) + 1)
            and set(retained) <= rows
            and len(set(retained)) == len(retained)
        )
    except (TypeError, KeyError):
        return False


def valid(state):
    items = list(_items(state))
    if not all(_section(item) for item in items):
        return False
    return _limits([item["root_details"] for item in items if item.get("root_details")])


def record(state, item, row, detail):
    section = item["root_details"]
    value = {**detail, "position_id": row[0], "outcome": row[1]}
    if value.get("reason") == "deadline":
        value["reason"] = row[2]
    turns = [turn for turn in section["turns"] if turn["position_id"] != row[0]]
    section = {**section, "turns": [*turns, value]}
    if room(state, item, section):
        item["root_details"] = section


def section(state, item):
    section = item.get("root_details")
    if section is not None:
        return section
    section = {"version": VERSION, "proof": PROOF_VERSION, "turns": [], "next": 0}
    item["root_details"] = section
    if room(state, item, section) and fits(state):
        return section
    item.pop("root_details")
    return None
