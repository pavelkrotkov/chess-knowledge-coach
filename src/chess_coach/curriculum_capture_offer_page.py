"""Publish the new capture offer without changing ordinary offer meaning."""

from .curriculum_capture_offer import issue
from .curriculum_priority_cursor import CAPTURE_POLICIES, COMMON_POLICY


def offer(db, value, item):
    state = value["state"]
    if (
        state.get("priority_policy") not in CAPTURE_POLICIES
        or item.get("source_type") != "own-game"
        or item.get("skill")
        not in (
            {"hanging_piece", "fork"}
            if state.get("priority_policy") == COMMON_POLICY
            else {"hanging_piece"}
        )
        or item.get("kind") != "new"
    ):
        return None
    window = value if "issued_at" in value else None
    return issue(db, state, item, value["goal"], value["expires_at"], window=window)


def untimed(db, state, page):
    value = {"state": state, "goal": "balanced", "expires_at": None}
    for item in page["items"]:
        token = offer(db, value, item)
        if token is not None:
            item["window_offer"] = token
