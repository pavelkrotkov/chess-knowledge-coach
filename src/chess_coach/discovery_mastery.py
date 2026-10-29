"""Keep discovery facts ineligible until an independent policy is qualified."""

from .discovery_contract import MAPPER


def closed(row):
    return bool(
        row["discovery_fact_count"]
        or row["mapping_producer"] == MAPPER
        or row["skill"] == "discovered_attack"
    )
