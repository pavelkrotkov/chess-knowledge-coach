"""Identity of the owned relative-pin slide objective."""

VERSION = "pin-relative-slide-own-v1"
OBJECTIVE = "pin-relative-slide-objective-v1"
GOAL = "defend_relative_pin_slide"
VERIFIER = "pin-relative-slide-verifier-v1"


def is_source(row):
    return (
        row["source_type"] == "own-game"
        and row["source_version"] == VERSION
        and row["objective"] == GOAL
    )
