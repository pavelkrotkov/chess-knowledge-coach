"""Require the exact mapper version and scope of each supported producer."""

from .back_rank_contract import MAPPER as BACK_RANK
from .back_rank_contract import VERSION as BACK_RANK_VERSION
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
    MATERIAL: (MATERIAL_VERSION, MATERIAL_SCOPE),
    "pin-execute-mapper": (PIN_VERSION, "pin-execute-v1"),
    "pin-prevent-mapper": (PIN_VERSION, "pin-prevent-v1"),
    FORK: (FORK_VERSION, FORK_SCOPE),
    DEFENSE: (DEFENSE_VERSION, DEFENSE_SCOPE),
    MATE: (MATE_VERSION, "bounded-mate-v1"),
    PAWN: (PAWN_VERSION, PAWN_SCOPE),
    "pawn-structure-lesson-mapper": ("1.1.0", "pawn-structure-lesson"),
}


def valid_scope(row):
    producer = row["mapping_producer"]
    if producer == BACK_RANK:
        expected = (BACK_RANK_VERSION, "back-rank-" + row["operation"])
    else:
        expected = SCOPES.get(producer)
    return expected == (row["mapper_version"], row["mapping_scope"])
