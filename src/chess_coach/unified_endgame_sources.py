"""Resolve subject-owned mate and pawn exercise sources."""

from .back_rank_practice_source import VERSION as BACK_RANK_VERSION
from .back_rank_practice_source import resolve as resolve_back_rank
from .discovery_practice import VERSION as DISCOVERY_VERSION
from .discovery_practice_source import resolve as resolve_discovery
from .mate_practice_source import VERSION as MATE_VERSION
from .mate_practice_source import resolve as resolve_mate
from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_capture_source import resolve as resolve_capture
from .objective_contract import VERSION as MATE_ONE_VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_defense_source import resolve as resolve_defense
from .objective_fork_contract import VERSION as FORK_VERSION
from .objective_fork_source import resolve as resolve_fork
from .objective_mate_source import resolve as resolve_mate_one
from .objective_pawn_contract import VERSION as PAWN_OBJECTIVE_VERSION
from .objective_pawn_source import resolve as resolve_pawn_objective
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_protection_source import resolve as resolve_protection
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_short_source import resolve as resolve_short
from .pawn_practice import VERSION as PAWN_VERSION
from .pawn_practice import resolve as resolve_pawn

VERSIONS = frozenset(
    (
        *CAPTURE_VERSIONS,
        PROTECTION_VERSION,
        PAWN_OBJECTIVE_VERSION,
        MATE_VERSION,
        PAWN_VERSION,
        BACK_RANK_VERSION,
        DISCOVERY_VERSION,
        MATE_ONE_VERSION,
        SHORT_VERSION,
        DEFENSE_VERSION,
        FORK_VERSION,
    )
)


OBJECTIVE_RESOLVERS = {
    FORK_VERSION: resolve_fork,
    DEFENSE_VERSION: resolve_defense,
    SHORT_VERSION: resolve_short,
    PROTECTION_VERSION: resolve_protection,
    PAWN_OBJECTIVE_VERSION: resolve_pawn_objective,
}


def resolve(db, version, key, subject):
    if version in CAPTURE_VERSIONS:
        return resolve_capture(db, version, key, subject)
    if version in OBJECTIVE_RESOLVERS:
        return OBJECTIVE_RESOLVERS[version](db, version, key, subject)
    if version == DISCOVERY_VERSION:
        return resolve_discovery(db, version, key, subject)
    if version == MATE_ONE_VERSION:
        return resolve_mate_one(db, version, key, subject)
    if version == MATE_VERSION:
        return resolve_mate(db, version, key, subject)
    if version == BACK_RANK_VERSION:
        return resolve_back_rank(db, version, key, subject)
    if version == PAWN_VERSION:
        return resolve_pawn(db, key, subject)
    raise ValueError("practice source unavailable")
