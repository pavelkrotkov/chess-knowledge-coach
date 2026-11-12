"""Map current coaching evidence to an existing owned-practice identity."""

from .fork_contract import MAPPER as FORK_MAPPER
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_current import current
from .objective_contract import VERSION as MATE_VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_fork_contract import VERSION as FORK_VERSION
from .objective_short_source import VERSION as SHORT_VERSION
from .unified_own_game import VERSION as MATERIAL_VERSION
from .unified_own_game_snapshot import key_for


def identity(db, subject, evidence):
    family, operation, skill = (
        evidence["mapping_producer"],
        evidence["operation"],
        evidence["skill"],
    )
    evidence_id = evidence["id"]
    if (family, skill, operation) == ("material-opportunity-mapper", "hanging_piece", "prevent"):
        view, _ = current(db, evidence_id, subject, kind="material_protection", operation="prevent")
        return MATERIAL_VERSION, key_for(view, evidence_id), "protection"
    supported = {
        (FORK_MAPPER, "fork", "execute"): (FORK_VERSION, "fork"),
        ("bounded-mate-observation-mapper", "mate_in_one", "execute"): (MATE_VERSION, "mate"),
        ("material-opportunity-mapper", "hanging_piece", "execute"): (TARGET_VERSION, "capture"),
        ("bounded-mate-observation-mapper", "calculation", "execute"): (
            SHORT_VERSION,
            "short_mate",
        ),
        ("back-rank-observation-mapper", "back_rank", "prevent"): (
            DEFENSE_VERSION,
            "back_rank_defense",
        ),
    }
    version, kind = supported.get((family, skill, operation), (None, None))
    if version is None:
        raise ValueError("practice unavailable")
    return version, str(evidence_id), kind
