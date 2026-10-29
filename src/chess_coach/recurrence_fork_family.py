"""Match fork recurrence to its exact execution or defense family."""

from .fork_contract import MAPPER as FORK_MAPPER


def fork_ok(row, fact):
    family, payload = row["mapping_producer"], fact["payload"]
    operation = "execute" if family == FORK_MAPPER else "prevent"
    kind = "fork" if family == FORK_MAPPER else "fork_defense"
    return (
        row["mapper_version"] == fact["detector_version"]
        and row["skill"] == "fork"
        and row["operation"] == operation
        and payload.get("kind") == kind
    )
