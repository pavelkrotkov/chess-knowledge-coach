"""Validate bounded mate observations for a coaching lesson."""

from .mate_selection import mapping_skill


def mate_supported(evidence, payload):
    return (
        payload["status"] == "opportunity"
        and mapping_skill(payload) == evidence["skill"]
        and payload["outcome"] == evidence["outcome"]
        and evidence["operation"] == "execute"
    )
