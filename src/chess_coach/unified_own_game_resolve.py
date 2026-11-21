"""Resolve subject-owned material exercises without exposing target squares."""

import chess

from .objective_capture_current import require_protection_scope
from .unified_endgame_sources import VERSIONS as ENDGAME_VERSIONS
from .unified_endgame_sources import resolve as resolve_endgame
from .unified_own_game import LEGACY_VERSION, VERSION
from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_keys import _parts, _positive
from .unified_own_game_legacy import _legacy
from .unified_own_game_snapshot import group_for, snapshot


def _current(db, subject, rows, kind, evidence_id, *, check=None):
    seen = set()
    # Check before each row; even duplicate groups need a currentness proof.
    for row in rows[:LIMIT]:
        if check is not None:
            check()
        view, review, reasons = _inspect(db, row["id"], subject, check=check)
        if reasons or view["objective"]["kind"] != kind:
            continue
        group = group_for(view)
        if group not in seen and row["id"] == evidence_id:
            require_protection_scope(db, evidence_id, subject, kind, check=check)
            return snapshot(view, review, row["id"])
        seen.add(group)
    raise ValueError("practice source unavailable")


def resolve(db, version, key, subject, *, check=None):
    if version in ENDGAME_VERSIONS:
        return resolve_endgame(db, version, key, subject)
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
    return _current(db, subject, rows, kind, _positive(suffix), check=check)
