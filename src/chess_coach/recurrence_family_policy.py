"""Recognize exact versioned fact and mapper contracts for recorded candidates."""

from .fork_contract import MAPPER as FORK_MAPPER
from .fork_contract import PRODUCER as FORK_PRODUCER
from .fork_contract import VERSION as FORK_VERSION
from .fork_defense_contract import MAPPER as DEFENSE_MAPPER
from .fork_defense_contract import PRODUCER as DEFENSE_PRODUCER
from .fork_defense_contract import VERSION as DEFENSE_VERSION
from .recurrence_proof_policy import mate_ok, pawn_ok

FAMILIES = {
    FORK_MAPPER: (FORK_PRODUCER, FORK_VERSION, "fork_opportunity"),
    DEFENSE_MAPPER: (DEFENSE_PRODUCER, DEFENSE_VERSION, "fork_defense_opportunity"),
    "bounded-mate-observation-mapper": ("bounded-mate-observation", "1.0.0", "bounded_mate"),
    "pawn-endgame-mapper": ("pawn-endgame-observation", "1.0.0", "pawn_endgame_opportunity"),
    "back-rank-observation-mapper": ("back-rank-observation", "1.0.0", "back_rank"),
}


def _fork_ok(row, fact):
    family, payload = row["mapping_producer"], fact["payload"]
    operation = "execute" if family == FORK_MAPPER else "prevent"
    kind = "fork" if family == FORK_MAPPER else "fork_defense"
    return (
        row["mapper_version"] == fact["detector_version"]
        and row["skill"] == "fork"
        and row["operation"] == operation
        and payload.get("kind") == kind
    )


def family_ok(row, fact):
    family = row["mapping_producer"]
    if FAMILIES.get(family) != (fact["producer"], fact["detector_version"], fact["fact_type"]):
        return False
    if fact["detector_version"] != fact["run_detector_version"]:
        return False
    if family in {FORK_MAPPER, DEFENSE_MAPPER}:
        return _fork_ok(row, fact)
    if family == "bounded-mate-observation-mapper":
        return mate_ok(row, fact)
    if family == "pawn-endgame-mapper":
        return pawn_ok(row, fact)
    return False
