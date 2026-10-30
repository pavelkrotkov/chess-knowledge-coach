"""Bind a report-scoped source snapshot to an owned purpose request."""

from .deep_selection_source import learner_key
from .purpose_request import fingerprint


def matches(snapshot, row, learner, config):
    return (
        isinstance(config, dict)
        and snapshot["learner_key"] == learner_key(learner)
        and snapshot["game_id"] == row["game_id"]
        and snapshot["position"]["id"] == row["position_id"]
        and fingerprint(snapshot, config) == row["request_fingerprint"]
    )
