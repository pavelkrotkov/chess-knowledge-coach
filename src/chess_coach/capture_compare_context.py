"""Validate recorded capture context before matching assessment cohorts."""

from .capture_compare_rules import checksum as checksum_valid
from .capture_compare_rules import mechanism, ratings, same
from .related_capture_assessment_context import VERSION


def _phases(context):
    return (
        context.get("content_phase") in {"middlegame", "endgame"}
        and context.get("source_phase") in {"middlegame", "endgame"}
        and context["same_phase"] == (context["content_phase"] == context["source_phase"])
    )


def _matching(context, content, source):
    flags = ("same_phase", "same_geometry", "same_opening", "same_material")
    distance = context.get("material_distance")
    return (
        all(type(context.get(key)) is bool for key in flags)
        and type(distance) is int
        and distance >= 0
        and context["same_material"] == (distance == 0)
        and context["same_geometry"] == (content["geometry"] == source["geometry"])
        and _phases(context)
    )


def valid(context):
    if not isinstance(context, dict) or context.get("version") != VERSION:
        return False
    content, source = context.get("mechanism"), context.get("source_mechanism")
    if not mechanism(content) or not mechanism(source):
        return False
    compatible = same(content, source)
    checksum = context.get("corpus_checksum")
    return (
        compatible
        and checksum_valid(checksum)
        and ratings(context)
        and _matching(context, content, source)
    )
