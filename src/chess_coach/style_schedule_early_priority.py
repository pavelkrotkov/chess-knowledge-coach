"""Prefer a feasible independent check/early-center pair in reserved cycles."""

from .style_schedule_budget import CURRENT


def _fits(check_count, center_count):
    budget = CURRENT.get()
    return budget is None or 2 * (check_count + center_count) <= budget["limit"] - budget["used"]


def _different(left, right):
    return left[0]["id"] != right[0]["id"] and (left[0]["pgn"], left[1]) != (
        right[0]["pgn"],
        right[1],
    )


def _check(ordered, nominations, center_index, center_count):
    for check_index, checks, _early, check_count in nominations:
        if (
            checks
            and _different(ordered[center_index], ordered[check_index])
            and _fits(check_count, center_count)
        ):
            return check_index
    return None


def pair(ordered, nominations):
    for center_index, _checks, early, center_count in nominations:
        if not early:
            continue
        check_index = _check(ordered, nominations, center_index, center_count)
        if check_index is not None:
            indexes = (check_index, center_index)
            return [ordered[index] for index in indexes] + [
                item for index, item in enumerate(ordered) if index not in indexes
            ]
    return None
