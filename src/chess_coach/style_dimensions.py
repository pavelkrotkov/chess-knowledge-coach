"""Classify contrasting endpoint proxies and conflicting alternatives."""

from .style_center import classify as center
from .style_check_choices import classify as checks
from .style_tradeoffs import classify as tradeoffs
from .style_transitions import classify as transitions


def classify(pair):
    return {**tradeoffs(pair), **transitions(pair), **center(pair), **checks(pair)}


def dimensions(pairs):
    found = {
        name: set()
        for name in (
            "simplification",
            "material_activity",
            "queenless",
            "low_material_transition",
            "center_contact",
            "center_pawn_capture",
            "center_pawn_exchange",
            "center_file_opening",
            "center_lock",
            "root_check",
            "conditional_check",
            "conditional_mate",
        )
    }
    for pair in pairs:
        for name, value in classify(pair).items():
            if value:
                found[name].add(value)
    return {name: _vote(values) for name, values in found.items()}


def _vote(values):
    if "ambiguous" in values or len(values) > 1:
        return "ambiguous"
    return next(iter(values)) if values else None
