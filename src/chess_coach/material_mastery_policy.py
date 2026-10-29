"""Gate mastery on the linked material source fact, not mapper labels."""

from .evidence_review_facts import facts_for_evidence
from .material_policy import MAPPER, fact_allowed


def mastery_allowed(db, row):
    if (
        row["mapping_producer"] == "bounded-mate-observation-mapper"
        or row["bounded_mate_fact_count"]
    ):
        return False
    if row["material_fact_count"] == 0:
        return row["mapping_producer"] != MAPPER
    if row["material_fact_count"] != 1 or row["link_count"] != 1:
        return False
    facts = facts_for_evidence(db, row["id"])
    return len(facts) == 1 and fact_allowed(
        facts[0], skill=row["skill"], operation=row["operation"], outcome=row["outcome"]
    )
