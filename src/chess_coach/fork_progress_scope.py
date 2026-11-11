"""Identify frozen knight-fork cohort context before source replay."""

import json

import chess

from .fork_comparison_context import CONTEXT_VERSION
from .related_capture_position import prompt_key


def scope(row, corpus):
    binding = json.loads(row["provenance_json"]).get("related_fork", {})
    assessment = binding.get("assessment")
    if not isinstance(assessment, dict):
        return None
    context = assessment.get("context")
    if not isinstance(context, dict):
        return None
    if (binding.get("motif"), binding.get("operation"), binding.get("pattern_cued")) != (
        "fork",
        "execute",
        True,
    ):
        return None
    if (context.get("version"), context.get("corpus"), context.get("attacker")) != (
        CONTEXT_VERSION,
        corpus,
        chess.KNIGHT,
    ):
        return None
    if any(
        type(context.get(key)) is not int or not 0 <= context[key] < limit
        for key, limit in (("rating_band", 20), ("deviation_band", 40))
    ):
        return None
    prompt_key(row["prompt_fen"])
    return context
