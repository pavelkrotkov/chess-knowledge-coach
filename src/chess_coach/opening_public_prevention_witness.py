"""Prove the two scoped public knight-fork prevention origins."""

from .fork_defense_probe import hypothetical
from .fork_defense_safety import quiet_after
from .opening_public_prevention_created import created
from .opening_public_prevention_existing import pre_existing


def inspect(board, recorded, clock, start, deadline, check, charge, max_alternatives, pending):
    if quiet_after(board, recorded) is None:
        return {origin: (None, "unsupported") for origin in pending}
    before = hypothetical(board, check=check)
    if before is None:
        return {origin: (None, "unsupported") for origin in pending}
    result = {}
    if "pre_existing" in pending:
        result["pre_existing"] = pre_existing(
            board, recorded, before, clock, start, deadline, check, charge, max_alternatives
        )
    if "created" in pending:
        result["created"] = created(
            board, recorded, before, clock, start, deadline, check, charge, max_alternatives
        )
    return result
