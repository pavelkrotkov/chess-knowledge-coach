"""Prefer a feasible independent check/early-center pair in reserved cycles."""

from .style_schedule_budget import CURRENT


def _fits(check_count, center_count):
    budget = CURRENT.get()
    return budget is None or 2 * (check_count + center_count) <= budget["limit"] - budget["used"]


def _check(nominations, center_key, center_count):
    for check_index, checks, _early, check_count, check_key in nominations:
        if (
            checks
            and check_key is not None
            and check_key != center_key
            and _fits(check_count, center_count)
        ):
            return check_index
    return None


def pair(ordered, nominations):
    for center_index, _checks, early, center_count, center_key in nominations:
        if not early or center_key is None:
            continue
        check_index = _check(nominations, center_key, center_count)
        if check_index is not None:
            indexes = (check_index, center_index)
            return [ordered[index] for index in indexes] + [
                item for index, item in enumerate(ordered) if index not in indexes
            ]
    return None
