"""Identify owned objectives whose assistance is tracked."""

from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_contract import VERSION as MATE_ONE_VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_pawn_contract import is_source as pawn_source
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_source import VERSION as SHORT_VERSION


def objective_assistance(row):
    return pawn_source(row) or (
        row["source_type"] == "own-game"
        and row["source_version"]
        in {MATE_ONE_VERSION, SHORT_VERSION, DEFENSE_VERSION, PROTECTION_VERSION, *CAPTURE_VERSIONS}
    )
