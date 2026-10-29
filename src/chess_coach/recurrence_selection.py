"""Bound expensive game replay and select relevant current-period sources."""

from .material_policy import MAPPER as MATERIAL_MAPPER
from .recurrence_candidates import candidate
from .recurrence_family_policy import FAMILIES
from .recurrence_game_cache import source
from .recurrence_recorded import period


def _period(row, excluded, begin, finish, previous):
    if row["mapping_status"] != "active" or row["review_decision"] in {"reject", "revoke"}:
        excluded["inactive or rejected"] += 1
        return None
    if row["mapping_producer"] not in FAMILIES and row["mapping_producer"] != MATERIAL_MAPPER:
        excluded["unsupported producer"] += 1
        return None
    selected = period(row["observation_at"], begin, finish, previous)
    if selected in {"unknown date", "outside window"}:
        excluded[selected] += 1
        return None
    return selected


def consider(
    db, learner, row, sources, cache, parts, excluded, begin, finish, previous, *, _history=None
):
    period = _period(row, excluded, begin, finish, previous)
    if period is None:
        return None
    game = source(db, learner, row, sources, cache, excluded)
    if game is None:
        return None
    item, reason = candidate(db, row, game, parts, _history=_history)
    if reason:
        excluded[reason] += 1
        return None
    item["period"] = period
    return item
