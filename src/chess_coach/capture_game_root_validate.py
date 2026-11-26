"""Validate optional root-section provenance before worker resume."""

from .capture_game_proof import VERSION as PROOF_VERSION
from .capture_game_root_budget import VERSION, _items, _limits


def _coverage(turn):
    roots, total, attempted = turn["roots"], turn["total"], turn["attempted"]
    # An unenumerated turn is unknown, not a known empty capture set.
    if total is None:
        return (roots, attempted, turn["unsearched"]) == ([], 0, None)
    return (
        type(attempted) is int
        and len(roots) <= attempted <= total
        and turn["unsearched"] == total - attempted
        and len({root[0] for root in roots}) == len(roots) <= 32
    )


def _section(item):
    section = item.get("root_details")
    if section is None:
        return True
    try:
        turns = section["turns"]
        rows = {(row[0], row[1]) for row in item["results"]}
        retained = {(turn["position_id"], turn["outcome"]) for turn in turns if _coverage(turn)}
        tag = (section["version"], section["proof"], type(turns))
        return (
            tag == (VERSION, PROOF_VERSION, list)
            and retained <= rows
            and len(retained) == len(turns)
        )
    except (TypeError, KeyError, IndexError):
        return False


def valid(games):
    if not all(map(_section, games)):
        return False
    return _limits(games)


def discard_invalid(state):
    for item in _items(state):
        if not _section(item):
            item.pop("root_details", None)
