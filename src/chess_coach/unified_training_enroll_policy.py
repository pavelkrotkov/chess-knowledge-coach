"""Select only the explicitly qualified learning policies."""

from .unified_corpus_mate import GOAL, is_source
from .unified_training_owned_capture import SOURCE as CAPTURE_SOURCE
from .unified_training_owned_capture import is_source as capture_source
from .unified_training_owned_fork import SOURCE as FORK_SOURCE
from .unified_training_owned_fork import is_source as fork_source
from .unified_training_public_mate import SOURCE as PUBLIC_SOURCE
from .unified_training_public_mate import is_source as public_source


def policy(row, goal, training, created):
    if not training or not created:
        raise ValueError("new qualified training is unavailable")
    if goal is None:
        return _owned_policy(row)
    if goal == GOAL and is_source(row):
        return None, None
    raise ValueError("new qualified training is unavailable")


def _owned_policy(row):
    if public_source(row):
        return PUBLIC_SOURCE, "mate_in_one"
    if capture_source(row):
        return CAPTURE_SOURCE, "hanging_piece"
    if fork_source(row):
        return FORK_SOURCE, "fork"
    raise ValueError("new qualified training is unavailable")
