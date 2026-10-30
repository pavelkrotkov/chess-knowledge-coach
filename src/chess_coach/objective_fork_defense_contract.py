"""Identity of the owned pre-existing knight-fork defense objective."""

VERSION = "fork-defense-own-v1"
OBJECTIVE = "fork-defense-objective-v1"
GOAL = "avoid_anchored_knight_fork"
VERIFIER = "fork-defense-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
