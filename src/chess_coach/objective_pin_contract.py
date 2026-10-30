"""Source-bound, bounded owned pin-creation objective."""

VERSION = "pin-execution-own-v1"
OBJECTIVE = "pin-execution-objective-v1"
GOAL = "execute_named_pin"
VERIFIER = "pin-execution-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
