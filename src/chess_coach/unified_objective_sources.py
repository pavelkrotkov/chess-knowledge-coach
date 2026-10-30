"""Owned objective source versions and their resolvers."""

from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_defense_source import resolve as resolve_defense
from .objective_fork_contract import VERSION as FORK_VERSION
from .objective_fork_defense_contract import VERSION as FORK_DEFENSE_VERSION
from .objective_fork_defense_source import resolve as resolve_fork_defense
from .objective_fork_source import resolve as resolve_fork
from .objective_pawn_contract import VERSION as PAWN_OBJECTIVE_VERSION
from .objective_pawn_source import resolve as resolve_pawn_objective
from .objective_pin_contract import VERSION as PIN_VERSION
from .objective_pin_source import resolve as resolve_pin
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_protection_source import resolve as resolve_protection
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_short_source import resolve as resolve_short

OBJECTIVE_RESOLVERS = {
    FORK_VERSION: resolve_fork,
    FORK_DEFENSE_VERSION: resolve_fork_defense,
    PIN_VERSION: resolve_pin,
    DEFENSE_VERSION: resolve_defense,
    SHORT_VERSION: resolve_short,
    PROTECTION_VERSION: resolve_protection,
    PAWN_OBJECTIVE_VERSION: resolve_pawn_objective,
}
