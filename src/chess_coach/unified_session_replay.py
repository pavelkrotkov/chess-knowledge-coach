"""Return the original immutable response for an idempotent event retry."""

import json


def previous(previous, kind, move, source_type):
    if (previous["kind"], previous["submitted_move"]) != (kind, move):
        raise ValueError("event ID belongs to another request")
    result = json.loads(previous["response_json"])
    if source_type == "own-game":
        result.pop("source_key", None)
        if result.get("objective") not in {
            "capture_named_target",
            "bounded_material_gain",
            "protect_threatened_piece",
        }:
            result.pop("objective_target", None)
    return result
