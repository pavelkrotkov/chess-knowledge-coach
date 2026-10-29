"""Resume legacy target-bearing keys without exposing them in output."""

from .unified_own_game_evidence import LIMIT, _inspect
from .unified_own_game_snapshot import group_for, snapshot


def _legacy(db, subject, rows, group):
    for row in rows[:LIMIT]:
        view, review, reasons = _inspect(db, row["id"], subject)
        if not reasons and group_for(view) == group:
            return snapshot(view, review, row["id"])
    raise ValueError("practice source unavailable")
