"""Match discovery recurrence to the precise observed skill and operation."""


def discovery_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "execute",
        "discovered_attack",
    )
