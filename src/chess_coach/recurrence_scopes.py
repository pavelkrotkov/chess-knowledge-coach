"""Require the exact mapper version and scope of each supported producer."""

from .back_rank_contract import MAPPER as BACK_RANK
from .back_rank_contract import VERSION as BACK_RANK_VERSION
from .discovery_contract import MAPPER as DISCOVERY
from .discovery_contract import SCOPE as DISCOVERY_SCOPE
from .discovery_contract import VERSION as DISCOVERY_VERSION
from .discovery_defense_contract import MAPPER as DISCOVERY_DEFENSE
from .discovery_defense_contract import SCOPE as DISCOVERY_DEFENSE_SCOPE
from .discovery_defense_contract import VERSION as DISCOVERY_DEFENSE_VERSION
from .discovery_mate_success_contract import MAPPER as DISCOVERY_SUCCESS
from .discovery_mate_success_contract import SCOPE as DISCOVERY_SUCCESS_SCOPE
from .discovery_mate_success_contract import VERSION as DISCOVERY_SUCCESS_VERSION
from .discovery_material_contract import MAPPER as DISCOVERY_MATERIAL
from .discovery_material_contract import SCOPE as DISCOVERY_MATERIAL_SCOPE
from .discovery_material_contract import VERSION as DISCOVERY_MATERIAL_VERSION
from .discovery_material_success_contract import MAPPER as MATERIAL_SUCCESS
from .discovery_material_success_contract import SCOPE as MATERIAL_SUCCESS_SCOPE
from .discovery_material_success_contract import VERSION as MATERIAL_SUCCESS_VERSION
from .fork_contract import MAPPER as FORK
from .fork_contract import SCOPE as FORK_SCOPE
from .fork_contract import VERSION as FORK_VERSION
from .fork_defense_contract import MAPPER as DEFENSE
from .fork_defense_contract import SCOPE as DEFENSE_SCOPE
from .fork_defense_contract import VERSION as DEFENSE_VERSION
from .mate_contract import MAPPER as MATE
from .mate_contract import MAPPER_VERSION as MATE_VERSION
from .material_contract import SCOPE as MATERIAL_SCOPE
from .material_contract import VERSION as MATERIAL_VERSION
from .material_policy import MAPPER as MATERIAL
from .pawn_coach_contract import MAPPER as PAWN
from .pawn_coach_contract import SCOPE as PAWN_SCOPE
from .pawn_coach_contract import VERSION as PAWN_VERSION
from .pin_pipeline import VERSION as PIN_VERSION

SCOPES = {
    MATERIAL_SUCCESS: (MATERIAL_SUCCESS_VERSION, MATERIAL_SUCCESS_SCOPE),
    DISCOVERY_SUCCESS: (DISCOVERY_SUCCESS_VERSION, DISCOVERY_SUCCESS_SCOPE),
    DISCOVERY_MATERIAL: (DISCOVERY_MATERIAL_VERSION, DISCOVERY_MATERIAL_SCOPE),
    DISCOVERY_DEFENSE: (DISCOVERY_DEFENSE_VERSION, DISCOVERY_DEFENSE_SCOPE),
    DISCOVERY: (DISCOVERY_VERSION, DISCOVERY_SCOPE),
    "king-safety-lesson-mapper": ("1.0.0", "king-safety-lesson"),
    MATERIAL: (MATERIAL_VERSION, MATERIAL_SCOPE),
    "pin-execute-mapper": (PIN_VERSION, "pin-execute-v1"),
    "pin-prevent-mapper": (PIN_VERSION, "pin-prevent-v1"),
    FORK: (FORK_VERSION, FORK_SCOPE),
    DEFENSE: (DEFENSE_VERSION, DEFENSE_SCOPE),
    MATE: (MATE_VERSION, "bounded-mate-v1"),
    PAWN: (PAWN_VERSION, PAWN_SCOPE),
    "pawn-structure-lesson-mapper": ("1.1.0", "pawn-structure-lesson"),
    "rook-plan-lesson-mapper": ("1.1.0", "rook-plan-lesson"),
}


def valid_scope(row):
    producer = row["mapping_producer"]
    if producer == BACK_RANK:
        expected = (BACK_RANK_VERSION, "back-rank-" + row["operation"])
    else:
        expected = SCOPES.get(producer)
    return expected == (row["mapper_version"], row["mapping_scope"])
