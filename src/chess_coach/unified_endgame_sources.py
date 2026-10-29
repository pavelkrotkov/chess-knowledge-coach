"""Resolve subject-owned mate and pawn exercise sources."""

from .back_rank_practice_source import VERSION as BACK_RANK_VERSION
from .back_rank_practice_source import resolve as resolve_back_rank
from .discovery_practice import VERSION as DISCOVERY_VERSION
from .discovery_practice_source import resolve as resolve_discovery
from .mate_practice_source import VERSION as MATE_VERSION
from .mate_practice_source import resolve as resolve_mate
from .pawn_practice import VERSION as PAWN_VERSION
from .pawn_practice import resolve as resolve_pawn

VERSIONS = frozenset((MATE_VERSION, PAWN_VERSION, BACK_RANK_VERSION, DISCOVERY_VERSION))


def resolve(db, version, key, subject):
    if version == DISCOVERY_VERSION:
        return resolve_discovery(db, version, key, subject)
    if version == MATE_VERSION:
        return resolve_mate(db, version, key, subject)
    if version == BACK_RANK_VERSION:
        return resolve_back_rank(db, version, key, subject)
    if version == PAWN_VERSION:
        return resolve_pawn(db, key, subject)
    raise ValueError("practice source unavailable")
