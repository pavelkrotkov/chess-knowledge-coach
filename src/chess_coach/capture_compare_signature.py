"""Canonical cohort signature for validated capture contexts."""

from .capture_compare_context import valid
from .fact_fingerprint import canonical
from .related_capture import VERSION as RANK_VERSION
from .related_capture_assessment import HISTORY, PROOF_VERSION, VERSION


def signature(context, corpus):
    if not valid(context):
        raise ValueError("capture context unavailable")
    baseline = context["ranking_baseline"]
    signature = [
        corpus,
        context["corpus_checksum"],
        "capture_named_target",
        RANK_VERSION,
        VERSION,
        PROOF_VERSION,
        HISTORY,
        context["mechanism"],
        context["source_mechanism"],
        context["content_phase"],
        context["source_phase"],
        context["same_phase"],
        context["same_geometry"],
        context["same_opening"],
        context["same_material"],
        context["material_distance"],
        None if baseline is None else baseline // 200,
        context["content_rating"] // 200,
        context["content_deviation"] // 100,
    ]
    return canonical(signature)
