"""Limit an explicit finder search to one current owned source."""

from .recurrence_cursor import _valid_id


def validate(position):
    if position is not None and not _valid_id(position):
        raise ValueError("capture source unavailable")
    return position


def restrict(groups, position):
    if position is None:
        return groups
    return {
        key: selected
        for key, items in groups.items()
        if (selected := [item for item in items if item["position_id"] == position])
    }


def option(raw):
    if raw is None:
        return {}
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 19:
        raise ValueError("capture source unavailable")
    return {"position": validate(int(raw))}


def search_options(expected):
    return {"expected": expected} if expected is not None else {}
