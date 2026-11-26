"""Publish the new capture offer without changing ordinary offer meaning."""

from .curriculum_capture_offer import issue
from .curriculum_priority_cursor import CAPTURE_POLICIES


def offer(db, value, item):
    state = value["state"]
    if (
        state.get("priority_policy") not in CAPTURE_POLICIES
        or item.get("source_type") != "own-game"
        or item.get("skill") != "hanging_piece"
        or item.get("kind") != "new"
    ):
        return None
    return issue(db, state, item, value["goal"], value["expires_at"])


def untimed(db, state, page):
    value = {"state": state, "goal": "balanced", "expires_at": None}
    for item in page["items"]:
        token = offer(db, value, item)
        if token is not None:
            item["window_offer"] = token
