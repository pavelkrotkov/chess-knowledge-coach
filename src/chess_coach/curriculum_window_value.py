"""Construct the unchanged signed practice-window envelope."""

from datetime import timedelta


def envelope(state, goal, minutes, page_limit, issued, policy):
    return {
        "v": 7,
        "policy": policy,
        "goal": goal,
        "minutes": minutes,
        "page_limit": page_limit,
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(minutes=minutes)).isoformat() if minutes else None,
        "state": state,
        "new_seen": [],
        "repeat_due": [],
        "source_refreshed": False,
        "selection_only": False,
    }
