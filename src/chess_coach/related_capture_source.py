"""Resolve current subject-owned capture observations and known positions."""

from .related_capture_admission import eligible_metadata
from .related_capture_context import _opening as _opening
from .related_capture_context import baseline as baseline
from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_snapshot import snapshot


def source_for_position(db, subject, position, *, check=None):
    tick = check or (lambda: None)
    for row in _rows(db, subject, position)[:LIMIT]:
        tick()
        try:
            eligible = eligible_metadata(db, row["id"])
        except (AttributeError, KeyError, TypeError, IndexError, ValueError):
            raise ValueError("capture source unavailable") from None
        if not eligible:
            continue
        options = {"check": check} if check is not None else {}
        view, review, reasons = _inspect(db, row["id"], subject, **options)
        tick()
        if reasons:
            raise ValueError("capture source unavailable")
        result = snapshot(view, review, row["id"])
        result["opening"] = _opening(db, position)
        return result
    raise ValueError("no current supported capture observation")
