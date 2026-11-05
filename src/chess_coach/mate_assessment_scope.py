"""Find truly like assessment content and matching-policy scopes."""

from .fact_fingerprint import canonical
from .mate_assessment_scope_valid import valid


def scope(row, binding, assessment):
    context = assessment.get("context")
    if not valid(context):
        return None
    rating, deviation = context["content_rating"], context["content_deviation"]
    mechanism = context["mechanism"]
    match = [context[key] for key in ("same_phase", "same_material", "same_opening")]
    baseline = context["ranking_baseline"]
    rating_start = rating // 200 * 200
    deviation_start = deviation // 100 * 100
    signature = [
        row["source_version"],
        context.get("corpus_checksum"),
        row["objective"],
        binding.get("rank_version"),
        binding.get("line_filter_version"),
        binding.get("operation"),
        binding.get("mate_timing"),
        assessment.get("version"),
        assessment.get("proof_version"),
        assessment.get("node_limit"),
        assessment.get("history_mode"),
        mechanism,
        context["content_phase"],
        context["source_phase"],
        match,
        context["material_distance"],
        None if baseline is None else baseline // 200,
        rating_start,
        deviation_start,
    ]
    return {
        "key": canonical(signature),
        "rating_start": rating_start,
        "deviation_start": deviation_start,
    }
