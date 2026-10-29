"""Route fork families to their independently qualified mastery policies."""

from .fork_defense_contract import MAPPER as DEFENSE_MAPPER
from .fork_defense_mastery import mastery_allowed as defense_allowed
from .fork_mastery_policy import mastery_allowed as execute_allowed


def family_reason(db, row):
    if _defense_source(row):
        return None if defense_allowed(db, row) else "fork_defense_family_unvalidated"
    return None if execute_allowed(db, row) else "fork_family_unvalidated"


def _defense_source(row):
    return (
        row["fork_defense_fact_count"]
        or row["mapping_producer"] == DEFENSE_MAPPER
        or (row["skill"] == "fork" and row["operation"] == "prevent")
    )
