"""Inspect recorded positions once per selected public history."""

import time

from .opening_public_prevention_example import bind
from .opening_public_prevention_witness import inspect as inspect_position

ORIGINS = ("pre_existing", "created")


def inspect_candidates(
    db,
    row,
    binding,
    identity,
    moves,
    first,
    last,
    candidates,
    censored,
    start,
    deadline,
    check,
    charge,
):
    policy = binding["policy"]["prevention"]
    states = {origin: ["completed_without_example", None] for origin in ORIGINS}
    for ply, board, recorded in reversed(candidates):
        check()
        if _inspect_position(
            db,
            row,
            binding,
            identity,
            moves,
            first,
            last,
            ply,
            board,
            recorded,
            start,
            deadline,
            check,
            charge,
            policy,
            states,
        ):
            return {key: tuple(value) for key, value in states.items()}, censored
    return {key: tuple(value) for key, value in states.items()}, censored


def _inspect_position(
    db,
    row,
    binding,
    identity,
    moves,
    first,
    last,
    ply,
    board,
    recorded,
    start,
    deadline,
    check,
    charge,
    policy,
    states,
):
    for origin in ORIGINS:
        example, reason = inspect_position(
            board,
            recorded,
            time.monotonic,
            start,
            deadline,
            check,
            charge,
            policy["alternatives_per_position"],
            {origin},
        )[origin]
        if example:
            bind(db, row, binding, identity, moves, first, last, ply, board, recorded, example)
            states[origin] = ["supported", example]
            for other in ORIGINS:
                if other != origin:
                    states[other][0] = "incomplete"
            return True
        if reason == "incomplete":
            states[origin][0] = "incomplete"
        elif reason and states[origin][0] != "incomplete":
            states[origin][0] = "unsupported"
    return False
