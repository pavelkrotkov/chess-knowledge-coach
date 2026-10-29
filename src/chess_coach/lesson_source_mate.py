"""Check bounded mate mapping semantics for lessons."""

from .mate_selection import mapping_skill


def mate(evidence, payload):
    return (
        payload["status"] == "opportunity"
        and mapping_skill(payload) == evidence["skill"]
        and payload["outcome"] == evidence["outcome"]
        and evidence["operation"] == "execute"
    )
