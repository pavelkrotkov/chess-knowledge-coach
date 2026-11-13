"""Revalidate owner, policy, configuration and source for a purpose request."""

import json

from .deep_selection_source import learner_key
from .purpose_config import EARLY_CENTER, PURPOSE, VERSION, configuration
from .purpose_snapshot_match import matches
from .purpose_source import source


def owned(db, request_id, learner):
    if type(request_id) is not int or request_id < 1:
        raise ValueError("purpose request is unavailable")
    row = db.connection.execute(
        "SELECT * FROM purpose_analysis_requests WHERE id=? AND learner_key=?",
        (request_id, learner_key(learner)),
    ).fetchone()
    if row is None:
        raise ValueError("purpose request is unavailable")
    return row


def current(db, row, learner, *, snapshot=None):
    if row["purpose"] != PURPOSE or row["policy_version"] not in (VERSION, EARLY_CENTER):
        raise ValueError("purpose request is stale")
    try:
        config = json.loads(row["config_json"])
        if snapshot is None:
            snapshot = source(db, row["position_id"], learner)
        fresh = configured(db, row, snapshot, config)
        if not matches(snapshot, row, learner, config) or config != fresh:
            raise ValueError("purpose request is stale")
    except (ValueError, TypeError, KeyError, RuntimeError, OSError):
        raise ValueError("purpose request is stale") from None
    return snapshot, config


# The historical policy continues to use its original configuration contract.
def configured(db, row, snapshot, config):
    if row["policy_version"] == EARLY_CENTER:
        from .purpose_early_center import roots

        if not roots(snapshot["board"], snapshot["position"]):
            raise ValueError("purpose request is stale")
        return configuration(db, snapshot["game_id"], config["engine_path"], policy=EARLY_CENTER)[1]
    return configuration(db, snapshot["game_id"], config["engine_path"])[1]
