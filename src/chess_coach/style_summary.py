"""Summarize the descriptive dimensions of a selected sample."""

from .style_counts import counts
from .style_strata import strata
from .style_trend import trend


def summarize(observations):
    return {
        name: {
            **counts(observations, name),
            "strata": strata(observations, name),
            "trend": trend(observations, name),
        }
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
