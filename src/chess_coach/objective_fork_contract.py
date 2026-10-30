"""Identity of the source-bound owned fork execution objective."""

VERSION = "fork-execution-own-v1"
OBJECTIVE = "fork-execution-objective-v1"
GOAL = "execute_named_fork"
VERIFIER = "fork-execution-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
