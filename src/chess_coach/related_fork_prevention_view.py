"""Expose a defensive prompt without revealing the selected line."""

import json


def add_fields(result, row):
    binding = json.loads(row["provenance_json"]).get("related_fork_prevention")
    if binding is not None:
        result["related_fork_prevention"] = True
