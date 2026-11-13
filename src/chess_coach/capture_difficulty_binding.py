"""Bind harder search candidates and admissions to their verified context."""

import json

from .fact_fingerprint import canonical, digest


def difficulty_scope(selection, difficulty):
    if difficulty is None or selection is None:
        return selection
    scope = digest(canonical([selection[4], "capture-harder-v1", difficulty]))
    items = [
        item
        for item in selection[3]
        if item["type"] == "corpus" and item["fen"].split()[1] == difficulty["side"][0]
    ]
    return (*selection[:3], items, scope, selection[5])


def options(difficulty):
    return {"rating_bounds": (difficulty["band"], difficulty["band"] + 199)} if difficulty else {}


def progression(binding, version, difficulty):
    if difficulty is None:
        return
    from .capture_compare_signature import signature

    context = json.loads(canonical(binding["assessment"]["context"]))
    if signature(context, version) != difficulty["expected"]:
        raise ValueError("harder capture context changed")
    binding["progression"] = {
        "policy": "capture-harder-v1",
        "prior_attempts": [difficulty["earlier"], difficulty["attempt"]],
    }


def decorate(result, expected, difficulty):
    result["items"][0]["assessment_available"] = True
    result["items"][0]["assessment_proved"] = True
    result["certified"] = True
    result["matched"] = expected is not None
    if difficulty:
        result.update(
            harder=True, harder_attempt=difficulty["attempt"], difficulty_band=difficulty["band"]
        )
    return result
