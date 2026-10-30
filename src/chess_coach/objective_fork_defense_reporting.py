"""Describe the aggregate reserved-work ceiling for fork-defense requests."""

from .objective_fork_avoidance_contract import OBJECTIVE as AVOIDANCE_OBJECTIVE
from .objective_fork_defense_budget import LIMIT
from .objective_fork_defense_contract import OBJECTIVE


def work_limit(rows):
    count = sum(row["objective_version"] in {OBJECTIVE, AVOIDANCE_OBJECTIVE} for row in rows)
    return (
        {"fork_defense_work_limit": {"requests": count, "fork_proof_units_cap": count * LIMIT}}
        if count
        else {}
    )
