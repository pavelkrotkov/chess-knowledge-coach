"""Validate due and corpus keyset coordinates."""

import math

from .curriculum_cursor_values import integer, text


def valid_due(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, list) or len(value) != 2:
        return False
    stamp = value[0]
    return (
        type(stamp) in (int, float)
        and math.isfinite(stamp)
        and 0 <= stamp <= 5373484
        and integer(value[1], 1, 2**63 - 1)
    )


def valid_new(value, pending: bool) -> bool:
    if value is None:
        return True
    length = 3 if pending else 2
    if not isinstance(value, list) or len(value) != length:
        return False
    if not _valid_pair(value):
        return False
    if not pending:
        return True
    return text(value[2], 64) and len(value[2]) == 64


def _valid_pair(value: list) -> bool:
    return integer(value[0], 0, 2**63 - 1) and text(value[1], 256)
