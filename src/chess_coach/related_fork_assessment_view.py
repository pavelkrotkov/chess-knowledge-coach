"""Expose only the announced unfamiliar fork roles."""

import json

from .objective_fork_view import add_fields
from .related_fork_assessment_scope import is_source


def add(result, row):
    if is_source(row):
        result["fork_assessment"] = True
        add_fields(result, json.loads(row["provenance_json"]))
