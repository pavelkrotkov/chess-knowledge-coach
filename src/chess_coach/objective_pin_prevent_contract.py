"""Identity of the owned, bounded pin-prevention objective."""

VERSION = "pin-prevention-own-v1"
OBJECTIVE = "pin-prevention-objective-v1"
GOAL = "prevent_named_pin"
VERIFIER = "pin-prevention-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
