"""Validate optional root-section provenance before worker resume."""

from .capture_game_proof import VERSION as PROOF_VERSION
from .capture_game_root_budget import VERSION, _items, _limits


def _section(item):
    section = item.get("root_details")
    if section is None:
        return True
    try:
        turns = section["turns"]
        rows = {(row[0], row[1]) for row in item["results"]}
        retained = [(turn["position_id"], turn["outcome"]) for turn in turns]
        tag = (section["version"], section["proof"], type(turns))
        return (
            tag == (VERSION, PROOF_VERSION, list)
            and set(retained) <= rows
            and len(set(retained)) == len(retained)
        )
    except (TypeError, KeyError):
        return False


def valid(games):
    if not all(_section(item) for item in games):
        return False
    return _limits([item["root_details"] for item in games if item.get("root_details")])


def discard_invalid(state):
    for item in _items(state):
        if not _section(item):
            item.pop("root_details", None)
