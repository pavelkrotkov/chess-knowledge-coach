"""Resolve subject-owned mate and pawn exercise sources."""

from .mate_practice_source import VERSION as MATE_VERSION
from .mate_practice_source import resolve as resolve_mate
from .pawn_practice import VERSION as PAWN_VERSION
from .pawn_practice import resolve as resolve_pawn

VERSIONS = frozenset((MATE_VERSION, PAWN_VERSION))


def resolve(db, version, key, subject):
    if version == MATE_VERSION:
        return resolve_mate(db, version, key, subject)
    if version == PAWN_VERSION:
        return resolve_pawn(db, key, subject)
    raise ValueError("practice source unavailable")
