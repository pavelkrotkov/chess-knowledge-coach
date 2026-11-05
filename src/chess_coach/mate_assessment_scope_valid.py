"""Check whether recorded admission context can support comparisons."""

from .related_mate_assessment_context import VERSION


def _numbers(context):
    rating, deviation = context.get("content_rating"), context.get("content_deviation")
    return type(rating) is int and type(deviation) is int and rating >= 0 and deviation >= 0


def _mechanism(context):
    mechanism = context.get("mechanism")
    return bool(mechanism and mechanism == context.get("source_mechanism"))


def _match(context):
    values = [context.get(key) for key in ("same_phase", "same_material", "same_opening")]
    baseline = context.get("ranking_baseline")
    distance = context.get("material_distance")
    return (
        type(distance) is int
        and distance >= 0
        and all(type(value) is bool for value in values)
        and (baseline is None or type(baseline) is int)
    )


def _phases(context):
    return context.get("content_phase") in {"middlegame", "endgame"} and context.get(
        "source_phase"
    ) in {"middlegame", "endgame"}


def valid(context):
    if not isinstance(context, dict):
        return False
    return (
        context.get("version") == VERSION
        and _numbers(context)
        and _mechanism(context)
        and bool(context.get("corpus_checksum"))
        and _phases(context)
        and "ranking_baseline" in context
        and _match(context)
    )
