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
        for name in ("simplification", "material_activity")
    }
