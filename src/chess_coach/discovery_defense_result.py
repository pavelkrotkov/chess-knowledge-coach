"""Verify the immediate defense and preserve the distinct threat witness."""

import time

from .discovery_defense_witness import witness
from .material_ambiguity import ambiguous
from .objective_defense_judge import judge

SECONDS = 1.0


def result(board, actual, best, compared, proof, started):
    answer = judge(board.copy(), best, time.monotonic, started, SECONDS, {})
    if answer["status"] != "correct":
        return ambiguous("discovery_mate_defense", "immediate_mate_scan_unresolved")
    anchor = witness(board, actual, best, proof, started + SECONDS)
    if anchor is None:
        return ambiguous("discovery_mate_defense", "positional_witness_unresolved")
    return {
        "kind": "discovery_mate_defense",
        "outcome": "failure",
        "played": compared["played"],
        "best": compared["best"],
        "threat": proof,
        "witness": anchor,
        "defense": {
            "move": best.uci(),
            "san": board.san(best),
            "legal_replies": answer["legal_replies"],
        },
        "boundary": "The positional witness is a tested alternative. The recorded continuation shows the mating threat after the played move. Longer consequences remain unknown.",
    }
