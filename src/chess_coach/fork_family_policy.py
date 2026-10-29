"""Keep fork families independently closed before validation."""

from .fork_defense_contract import MAPPER as DEFENSE_MAPPER


def closed_reason(row):
    if row["fork_defense_fact_count"] or row["mapping_producer"] == DEFENSE_MAPPER:
        return "fork_defense_family_unvalidated"
    return None
