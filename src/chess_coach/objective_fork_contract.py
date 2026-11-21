"""Identity of the source-bound owned fork execution objective."""

VERSION = "fork-execution-own-v1"
OBJECTIVE = "fork-execution-objective-v1"
MISS_VERSION = "fork-execution-own-v2"
MISS_OBJECTIVE = "fork-execution-objective-v2"
MISS_VERIFIER = "fork-execution-verifier-v2"
GOAL = "execute_named_fork"
VERIFIER = "fork-execution-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] in {VERSION, MISS_VERSION}
        and row["objective"] == GOAL
    )


def is_miss_source(row):
    return is_source(row) and row["source_version"] == MISS_VERSION
