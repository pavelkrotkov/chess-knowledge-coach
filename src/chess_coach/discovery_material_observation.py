"""Prove a recorded-choice material exposure and one named defense."""

import time

from .discovery_defense_input import setup
from .discovery_geometry import discoveries
from .discovery_material_assess import assess
from .discovery_proof import prove
from .material_ambiguity import ambiguous


def observe(board, played, best_line, played_line, *, started=None):
    started = time.monotonic() if started is None else started
    values = setup(board, played, best_line, played_line)
    if values is None:
        return None
    actual, after, best, _compared, attack = values
    if not discoveries(after, attack):
        return None

    def check():
        if time.monotonic() - started >= 1.0:
            raise TimeoutError

    try:
        proofs = [proof for proof in prove(after, attack, check=check) if not proof["mate"]]
        check()
        if not proofs:
            return ambiguous("discovery_material_defense", "material_consequence_unresolved")
        return assess(board, actual, best, best_line, played_line, proofs[0], started, check)
    except TimeoutError:
        return ambiguous("discovery_material_defense", "proof_deadline_exhausted")
