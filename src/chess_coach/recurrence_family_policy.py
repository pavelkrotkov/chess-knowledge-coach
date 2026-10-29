"""Recognize exact versioned fact and mapper contracts for recorded candidates."""

from .fork_contract import MAPPER as FORK_MAPPER
from .fork_contract import PRODUCER as FORK_PRODUCER
from .fork_contract import VERSION as FORK_VERSION
from .fork_defense_contract import MAPPER as DEFENSE_MAPPER
from .fork_defense_contract import PRODUCER as DEFENSE_PRODUCER
from .fork_defense_contract import VERSION as DEFENSE_VERSION
from .king_safety_recurrence import king_ok
from .recurrence_fork_policy import fork_family_ok
from .recurrence_pin_policy import PIN_FAMILIES, pin_family_ok
from .recurrence_proof_policy import backrank_ok, mate_ok, pawn_ok
from .recurrence_rook_policy import rook_ok

FAMILIES = {
    **PIN_FAMILIES,
    "king-safety-lesson-mapper": ("king-safety-lesson", "1.0.0", "king_safety_lesson"),
    FORK_MAPPER: (FORK_PRODUCER, FORK_VERSION, "fork_opportunity"),
    DEFENSE_MAPPER: (DEFENSE_PRODUCER, DEFENSE_VERSION, "fork_defense_opportunity"),
    "bounded-mate-observation-mapper": ("bounded-mate-observation", "1.0.0", "bounded_mate"),
    "pawn-endgame-mapper": ("pawn-endgame-observation", "1.0.0", "pawn_endgame_opportunity"),
    "back-rank-observation-mapper": ("back-rank-observation", "1.0.0", "back_rank"),
    "pawn-structure-lesson-mapper": ("pawn-structure-lesson", "1.1.0", "pawn_structure_lesson"),
    "rook-plan-lesson-mapper": ("rook-plan-lesson", "1.1.0", "rook_plan_lesson"),
}


def _structure_ok(row, fact):
    return (
        (row["skill"], row["operation"], row["outcome"])
        == ("pawn_structure", "evaluate", "ambiguous")
        and fact["payload"].get("version") == "1.1.0"
        and fact["payload"].get("mastery_eligible") is False
    )


VALIDATORS = {
    "king-safety-lesson-mapper": king_ok,
    "rook-plan-lesson-mapper": rook_ok,
    FORK_MAPPER: fork_family_ok,
    DEFENSE_MAPPER: fork_family_ok,
    "bounded-mate-observation-mapper": mate_ok,
    "pawn-endgame-mapper": pawn_ok,
    "back-rank-observation-mapper": backrank_ok,
    "pawn-structure-lesson-mapper": _structure_ok,
}


def family_ok(row, fact):
    family = row["mapping_producer"]
    if FAMILIES.get(family) != (fact["producer"], fact["detector_version"], fact["fact_type"]):
        return False
    if fact["detector_version"] != fact["run_detector_version"]:
        return False
    if family in PIN_FAMILIES:
        return pin_family_ok(row, fact)
    validator = VALIDATORS.get(family)
    return validator(row, fact) if validator else False
