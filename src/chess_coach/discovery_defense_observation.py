"""Verify a recorded quiet choice, discovered mate and an immediate defense."""

import time

from .discovery_defense_input import setup
from .discovery_defense_mate import mating
from .discovery_defense_result import result
from .discovery_geometry import discoveries
from .material_ambiguity import ambiguous


def observe(board, played, best_line, played_line):
    started = time.monotonic()
    values = setup(board, played, best_line, played_line)
    if values is None:
        return None
    actual, after, best, compared, attack = values
    proofs = mating(after, attack)
    if not proofs:
        return (
            ambiguous("discovery_mate_defense", "discovered_consequence_unresolved")
            if discoveries(after, attack)
            else None
        )
    return result(board, actual, best, compared, proofs[0], started)
