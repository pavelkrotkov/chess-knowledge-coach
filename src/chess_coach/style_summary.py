"""Summarize the descriptive dimensions of a selected sample."""

from .style_counts import counts
from .style_defense_choices import NAMES as DEFENSE_NAMES
from .style_protection_choices import NAMES as PROTECTION_NAMES
from .style_strata import strata
from .style_trend import trend


def summarize(observations):
    return {
        name: {
            **counts(_eligible(observations, name), name),
            "strata": strata(_eligible(observations, name), name),
            "trend": trend(_eligible(observations, name), name),
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
            *DEFENSE_NAMES,
            *PROTECTION_NAMES,
        )
    }


def _eligible(observations, name):
    return [
        item
        for item in observations
        if item.get("eligible_dimensions") is None or name in item["eligible_dimensions"]
    ]
