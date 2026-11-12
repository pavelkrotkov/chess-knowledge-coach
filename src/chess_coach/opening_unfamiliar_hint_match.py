"""Validate optional comparison artifact hints against their named context."""

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .opening_queue_binding import identity


def _payload(value):
    if not isinstance(value, dict) or not isinstance(value.get("measurement"), dict):
        return None
    payload = value["measurement"]
    if not all(isinstance(payload.get(key), dict) for key in ("source", "configuration", "result")):
        return None
    if value.get("sha256") != digest(canonical(payload)):
        return None
    return payload


def matching(value, match, database, learner, parent, item):
    payload = _payload(value)
    if payload is None:
        return None
    source, config = payload["source"], payload["configuration"]
    actual = (
        payload.get("version"),
        payload["result"].get("status"),
        identity(database, source, config),
        source.get("learner_key"),
        source.get("decision_fen"),
        source.get("alternative"),
        source.get("child"),
        type(source.get("game_id")),
    )
    expected = (
        "opening-catalog-measurement-v1",
        "complete",
        match.group(1),
        learner_key(learner),
        parent,
        item["uci"],
        item["child_key"],
        int,
    )
    return source["game_id"] if actual == expected else None
