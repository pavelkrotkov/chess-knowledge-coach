"""Expose transfer context without revealing the selected line."""

import json


def add_fields(result, row):
    if json.loads(row["provenance_json"]).get("related_backrank_attack") is not None:
        result["related_backrank_attack"] = True
