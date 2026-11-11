"""Inspect one current analysis under a cooperative turn deadline."""

import time

from .fork_game_proof import Deadline
from .fork_miss_source import configuration, marker
from .fork_miss_verify import verify


def _check(deadline):
    if time.monotonic() >= deadline:
        raise Deadline()


def _entry(db, learner, game, position, outcome, deadline):
    before = marker(db, game, position, learner)
    try:
        try:
            status, source = verify(db, learner, position, outcome, lambda: _check(deadline))
            config = configuration(db, source)
        except (ValueError, TypeError, KeyError, IndexError):
            status, config = "unresolved", None
        _check(deadline)
        if marker(db, game, position, learner) != before:
            raise ValueError("analysis changed")
        _check(deadline)
    except Deadline:
        return [game, before, "retry", None]
    return [game, before, status, config]
