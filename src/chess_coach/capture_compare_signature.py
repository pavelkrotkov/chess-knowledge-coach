"""Canonical cohort signature for validated capture contexts."""

from .capture_compare_context import valid
from .fact_fingerprint import canonical
from .related_capture import VERSION as RANK_VERSION
from .related_capture_assessment import HISTORY, PROOF_VERSION, VERSION


def _components(context, corpus, *, rating_start=None):
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
        (context["content_rating"] if rating_start is None else rating_start) // 200,
        context["content_deviation"] // 100,
    ]
    return signature


def signature(context, corpus, *, rating_start=None):
    if not valid(context):
        raise ValueError("capture context unavailable")
    return canonical(_components(context, corpus, rating_start=rating_start))


def projections(context, corpus):
    """Separate validated shared controls from the original source pattern."""
    values = _components(context, corpus)
    names = (
        "corpus",
        "checksum",
        "objective",
        "rank_policy",
        "assessment_policy",
        "proof_policy",
        "history",
        "content_phase",
        "source_phase",
        "same_phase",
        "same_geometry",
        "same_opening",
        "same_material",
        "material_distance",
        "baseline_band",
        "rating_band",
        "deviation_band",
    )
    return dict(zip(names, values[:7] + values[9:], strict=True)), values[8]
