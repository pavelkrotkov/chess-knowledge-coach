"""Apply the same supported fact contracts to standalone decision lessons."""

from .back_rank_outcomes import outcomes
from .lesson_mate_policy import mate_supported
from .lesson_rook_policy import rook_supported
from .lesson_structure_policy import structure_supported
from .material_opportunity_links import valid_link
from .material_policy import fact_allowed


def _supported(db, evidence, fact):
    family, payload = evidence["mapping_producer"], fact["payload"]
    if family == "material-opportunity-mapper":
        return fact_allowed(
            fact,
            skill=evidence["skill"],
            operation=evidence["operation"],
            outcome=evidence["outcome"],
        )
    if family == "bounded-mate-observation-mapper":
        return mate_supported(evidence, payload)
    descriptive = {
        "pawn-structure-lesson-mapper": structure_supported,
        "rook-plan-lesson-mapper": rook_supported,
    }
    if family in descriptive:
        return descriptive[family](db, evidence, fact)
    if family == "back-rank-observation-mapper":
        return evidence["skill"] == "back_rank" and (
            evidence["operation"],
            evidence["outcome"],
        ) in outcomes(payload)
    return True


def supported(db, evidence):
    facts = evidence["facts"]
    if len(facts) != 1 or not valid_link(db, evidence, facts[0]):
        return False
    try:
        return _supported(db, evidence, facts[0])
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
