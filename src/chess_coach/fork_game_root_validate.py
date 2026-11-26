"""Validate optional fork root coverage without inferring missing records."""

from .capture_game_root_budget import _items, _limits
from .capture_game_root_validate import _coverage
from .fork_game_proof import VERSION
from .fork_game_root_detail import POLICY


def _section(item):
    section = item.get("root_details")
    if section is None:
        return True
    try:
        turns = section["turns"]
        rows = {tuple(row) for row in item["results"]}
        retained = set()
        for turn in turns:
            if not _coverage(turn):
                return False
            retained.add((turn["position_id"], turn["outcome"], turn["reason"]))
        return (
            (section["version"], section["proof"], type(turns)) == (POLICY, VERSION, list)
            and retained <= rows
            and len(retained) == len(turns)
        )
    except (TypeError, KeyError, IndexError):
        return False


def valid(data):
    items = list(_items(data))
    return _limits(items) and all(map(_section, items))
