"""Resolve subject-owned material exercises without exposing target squares."""

import chess

from .unified_own_game import LEGACY_VERSION, VERSION
from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_keys import _parts, _positive
from .unified_own_game_legacy import _legacy
from .unified_own_game_snapshot import group_for, snapshot


def _current(db, subject, rows, kind, evidence_id):
    seen = set()
    for row in rows[:LIMIT]:
        view, review, reasons = _inspect(db, row["id"], subject)
        if reasons or view["objective"]["kind"] != kind:
            continue
        group = group_for(view)
        if group in seen:
            continue
        seen.add(group)
        if row["id"] == evidence_id:
            return snapshot(view, review, row["id"])
    raise ValueError("practice source unavailable")


def resolve(db, version, key, subject):
    position, kind, suffix = _parts(key)
    rows = _rows(db, subject, position)
    if version == LEGACY_VERSION:
        try:
            chess.parse_square(suffix)
        except ValueError:
            raise ValueError("practice source unavailable") from None
        return _legacy(db, subject, rows, (position, kind, suffix))
    if version != VERSION:
        raise ValueError("practice source unavailable")
    return _current(db, subject, rows, kind, _positive(suffix))
