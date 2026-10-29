"""Apply the same supported fact contracts to standalone decision lessons."""

from .back_rank_outcomes import outcomes
from .mate_selection import mapping_skill
from .material_opportunity_links import valid_link
from .material_policy import fact_allowed


def _mate(evidence, payload):
    return (
        payload["status"] == "opportunity"
        and mapping_skill(payload) == evidence["skill"]
        and payload["outcome"] == evidence["outcome"]
        and evidence["operation"] == "execute"
    )


def supported(db, evidence):
    facts = evidence["facts"]
    if len(facts) != 1 or not valid_link(db, evidence, facts[0]):
        return False
    fact = facts[0]
    family, payload = evidence["mapping_producer"], fact["payload"]
    try:
        if family == "material-opportunity-mapper":
            return fact_allowed(
                fact,
                skill=evidence["skill"],
                operation=evidence["operation"],
                outcome=evidence["outcome"],
            )
        if family == "bounded-mate-observation-mapper":
            return _mate(evidence, payload)
        if family == "back-rank-observation-mapper":
            return evidence["skill"] == "back_rank" and (
                evidence["operation"],
                evidence["outcome"],
            ) in outcomes(payload)
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
