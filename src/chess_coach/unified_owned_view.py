"""Expose owned-practice metadata without the private source key."""

import json

from .objective_fork_view import add_fields as add_fork_fields


def add_fields(result, row):
    provenance = json.loads(row["provenance_json"])
    result["review_status"] = provenance["review_status"]
    result["evidence_id"] = provenance["evidence_id"]
    result["position_id"] = provenance["position_id"]
    if row["objective"] == "execute_named_pin":
        for key in ("pin_attacker", "pin_pinned", "pin_rear", "pin_type"):
            result[key] = provenance[key]
    if row["objective"] == "execute_named_fork":
        add_fork_fields(result, provenance)
    if row["objective"] in {"capture_named_target", "protect_threatened_piece"}:
        result["objective_target"] = provenance["objective_target"]
    if row["objective"] in {
        "capture_named_target",
        "bounded_material_gain",
        "protect_threatened_piece",
    }:
        result["gain_threshold"] = provenance["gain_threshold"]
    result.pop("source_key", None)
