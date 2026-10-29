"""Expose the named fork objective without its exemplar or proof."""


def add_fields(result, provenance):
    result["fork_attacker"] = provenance["fork_attacker"]
    result["fork_anchor"] = provenance["fork_anchor"]
    result["gain_threshold"] = provenance["gain_threshold"]
    result["source_outcome"] = provenance["source_outcome"]
