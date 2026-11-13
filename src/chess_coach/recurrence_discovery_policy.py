"""Match discovery recurrence to the precise observed skill and operation."""


def discovery_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "execute",
        "discovered_attack",
    )


def discovery_defense_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "prevent",
        "discovery_mate_defense",
    )


def discovery_material_ok(row, fact):
    return (row["skill"], row["operation"], fact["payload"].get("kind")) == (
        "discovered_attack",
        "prevent",
        "discovery_material_defense",
    )
