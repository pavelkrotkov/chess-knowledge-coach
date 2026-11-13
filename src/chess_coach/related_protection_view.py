"""Expose the named defensive goal without exposing the supplied line."""

import json


def add_fields(result, row):
    binding = json.loads(row["provenance_json"]).get("related_protection")
    if binding is not None:
        result["related_protection"] = True
        result["protection_assessment"] = bool(binding.get("assessment"))
        result["protection_target"] = binding["objective_target"]
        if result["protection_assessment"]:
            result["objective_target"] = binding["objective_target"]
        result["gain_threshold"] = binding["gain_threshold"]
