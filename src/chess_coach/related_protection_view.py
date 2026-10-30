"""Expose the named defensive goal without exposing the supplied line."""

import json


def add_fields(result, row):
    binding = json.loads(row["provenance_json"]).get("related_protection")
    if binding is not None:
        result["related_protection"] = True
        result["protection_target"] = binding["objective_target"]
        result["gain_threshold"] = binding["gain_threshold"]
