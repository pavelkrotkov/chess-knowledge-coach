"""Expose transfer context without revealing the selected line."""

import json


def add_fields(result, row):
    data = json.loads(row["provenance_json"])
    if data.get("related_backrank_attack") is not None:
        result["related_backrank_attack"] = True
    defense = data.get("related_backrank_defense")
    if defense is not None:
        result["related_backrank_defense"] = True
        result["related_backrank_defense_origin"] = defense.get(
            "threat_origin", "anchored_preexisting"
        )
        if row["status"] == "line_completed":
            result["backrank_defense_witness"] = defense["defense_witness"]
