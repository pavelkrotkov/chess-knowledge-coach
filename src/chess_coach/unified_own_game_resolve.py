"""Resolve a deduplicated position and material objective for its subject."""

import chess

from .unified_own_game import VERSION
from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_snapshot import KINDS, key_for, snapshot


def _parse_key(key):
    try:
        position, kind, target = key.split(":")
        number = int(position)
        if number <= 0 or str(number) != position or kind not in KINDS:
            raise ValueError
        chess.parse_square(target)
    except (ValueError, TypeError):
        raise ValueError("practice source unavailable") from None
    return number


def resolve(db, version, key, subject):
    if version != VERSION:
        raise ValueError("practice source unavailable")
    position = _parse_key(key)
    rows = _rows(db, subject, position)
    for row in rows[:LIMIT]:
        view, review, reasons = _inspect(db, row["id"], subject)
        if not reasons and key_for(view) == key:
            return snapshot(view, review, row["id"])
    raise ValueError("practice source unavailable")
