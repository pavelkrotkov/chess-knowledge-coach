"""Expose only the announced unfamiliar fork roles."""

import json

from .objective_fork_view import add_fields
from .related_fork_assessment_scope import is_source


def add(result, row):
    if is_source(row):
        provenance = json.loads(row["provenance_json"])
        result["fork_assessment"] = True
        result["fork_comparison_context"] = bool(
            provenance["related_fork"]["assessment"].get("context")
        )
        add_fields(result, provenance)
