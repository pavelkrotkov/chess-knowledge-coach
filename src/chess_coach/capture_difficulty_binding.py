"""Bind harder search candidates and admissions to their verified context."""

import json
from functools import partial

from .fact_fingerprint import canonical, digest
from .related_capture_match import candidate


def difficulty_scope(selection, difficulty):
    if difficulty is None or selection is None:
        return selection
    scope = digest(canonical([selection[4], "capture-harder-v1", difficulty]))
    return (*selection[:4], scope, selection[5])


def _score(raw, source, seen, baseline, *, side):
    if raw["type"] != "corpus":
        return None
    item = candidate(raw, source, seen, baseline)
    return item if item and item["fen"].split()[1] == side[0] else None


def options(difficulty):
    if difficulty is None:
        return {}
    return {
        "rating_bounds": (difficulty["band"], difficulty["band"] + 199),
        "score": partial(_score, side=difficulty["side"]),
    }


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
