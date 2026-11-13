"""The narrow discovered-mate first-answer transfer."""

import json

KEY = "related_discovery_mate"
VERSION = "discovery-mate-transfer-v1"
FILTER_VERSION = "discovery-mate-lines-v1"
OBJECTIVE = "discovery_mate_in_one"


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != OBJECTIVE:
        return False
    binding = json.loads(row["provenance_json"]).get(KEY)
    return isinstance(binding, dict) and (
        binding.get("rank_version"),
        binding.get("motif"),
        binding.get("operation"),
    ) == (VERSION, "discovery_mate", "execute")


def apply(snapshot, key):
    if key == KEY:
        snapshot["objective"] = OBJECTIVE


def recheck(db, row, binding, source, snapshot_hash):
    from .related_capture_assessment import setup
    from .related_discovery_source import shape
    from .related_fork_lines import select_lines
    from .unified_sources import resolve_source

    selected = resolve_source(
        db, row["source_type"], row["source_version"], row["source_key"], subject=row["subject"]
    )
    select_lines(selected, binding, expected_version=FILTER_VERSION)
    board, moves, _ = setup(db, row["source_version"], row["source_key"])
    if board.fen() != selected["prompt_fen"] or len(moves) != 2:
        raise ValueError("discovered mate setup changed")
    features = shape(board, board.parse_uci(moves[1]))
    if not features or features["geometry"] != source["features"]["geometry"]:
        raise ValueError("discovered mate proof changed")
    selected["objective"] = OBJECTIVE
    selected["provenance"][KEY] = binding
    if snapshot_hash(selected) != row["snapshot_hash"]:
        raise ValueError("discovered mate snapshot changed")
