"""Parse bounded practice keys without exposing their private objective."""

from .unified_own_game_snapshot import KINDS


def _positive(value):
    try:
        number = int(value)
        if number <= 0 or number > 2**63 - 1 or str(number) != value:
            raise ValueError
        return number
    except (ValueError, TypeError):
        raise ValueError("practice source unavailable") from None


def _parts(key):
    try:
        position, kind, suffix = key.split(":")
        position = _positive(position)
        if kind not in KINDS:
            raise ValueError
        return position, kind, suffix
    except (ValueError, TypeError):
        raise ValueError("practice source unavailable") from None
