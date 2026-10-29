"""Apply the ordered family-specific mastery gates."""

from .back_rank_mastery import closed as back_rank_closed
from .discovery_mastery import closed as discovery_closed
from .fork_family_policy import family_reason
from .king_safety_mastery import closed as king_safety_closed
from .mate_mastery_policy import mastery_allowed as mate_mastery_allowed
from .material_mastery_policy import mastery_allowed
from .pawn_mastery_policy import mastery_allowed as pawn_mastery_allowed
from .pin_mastery import closed as pin_closed


def family_exclusion(db, row):
    closed_reason = _closed_reason(row)
    if closed_reason:
        return closed_reason
    if back_rank_closed(row):
        return "back_rank_family_unvalidated"
    if not mate_mastery_allowed(db, row):
        return "mate_family_unvalidated"
    if not pawn_mastery_allowed(db, row):
        return "pawn_family_unvalidated"
    reason = family_reason(db, row)
    if reason:
        return reason
    if not mastery_allowed(db, row):
        return "material_family_unvalidated"
    return None


def _closed_reason(row):
    if discovery_closed(row):
        return "discovery_family_unvalidated"
    if pin_closed(row):
        return "pin_family_unvalidated"
    if king_safety_closed(row):
        return "king_safety_family_unvalidated"
    return None
