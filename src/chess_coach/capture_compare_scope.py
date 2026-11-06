"""Bind comparable capture assessments to their recorded matching policy."""

import json

from .capture_compare_context import valid
from .capture_compare_signature import signature
from .related_capture import VERSION as RANK_VERSION
from .related_capture_assessment import HISTORY, PROOF_VERSION, VERSION


def _binding(binding, assessment):
    if binding.get("pattern_cued") is not True:
        return False
    if (
        binding.get("rank_version"),
        binding.get("motif"),
        binding.get("operation"),
        binding.get("pattern_cued"),
    ) != (RANK_VERSION, "material_capture", "execute", True):
        return False
    return (
        assessment.get("version"),
        assessment.get("proof_version"),
        assessment.get("history_mode"),
        assessment.get("gain_threshold"),
    ) == (VERSION, PROOF_VERSION, HISTORY, 3)


def scope(row, corpus):
    if (row["source_type"], row["source_version"], row["objective"]) != (
        "corpus",
        corpus,
        "capture_named_target",
    ):
        return None
    binding = json.loads(row["provenance_json"]).get("related_capture")
    if not isinstance(binding, dict) or not isinstance(binding.get("assessment"), dict):
        return None
    assessment = binding["assessment"]
    if not _binding(binding, assessment):
        return None
    context = assessment.get("context")
    if not valid(context):
        return None
    return {
        "key": signature(context, corpus),
        "rating_start": context["content_rating"] // 200 * 200,
        "deviation_start": context["content_deviation"] // 100 * 100,
    }
