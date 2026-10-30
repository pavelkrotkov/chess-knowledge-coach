"""Distinct owned created-fork avoidance objective identity."""

VERSION = "fork-avoidance-own-v1"
OBJECTIVE = "fork-avoidance-objective-v1"
GOAL = "avoid_created_knight_fork"
VERIFIER = "fork-avoidance-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
