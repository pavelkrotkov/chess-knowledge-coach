"""Expose the named fork objective without its exemplar or proof."""

from .objective_fork_contract import is_miss_source


def add_fields(result, provenance, *, row=None):
    result["fork_attacker"] = provenance["fork_attacker"]
    result["fork_anchor"] = provenance["fork_anchor"]
    result["gain_threshold"] = provenance["gain_threshold"]
    result["source_outcome"] = provenance["source_outcome"]

    if row is not None and is_miss_source(row):
        result["fork_objective_miss_policy"] = True
