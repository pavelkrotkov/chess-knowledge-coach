"""Verify an observed defense and a legal counterfactual threat anchor."""

from .fork_defense_anchor import anchor
from .material_ambiguity import ambiguous
from .material_lines import continuation


def success(board, actual, played_line, candidates, *, check=None, on_proof=None):
    witness = anchor(board, candidates, check=check, on_proof=on_proof)
    if witness is None:
        return ambiguous("fork_defense", "threat_anchor_unverified")
    if "reason" in witness:
        return ambiguous("fork_defense", witness["reason"])
    if check is not None:
        check()
    played = continuation(board, played_line, actual.uci())
    if played is None or played["material_delta"] < 0:
        return ambiguous("fork_defense", "continuation_or_compensation_unresolved")
    return {
        "kind": "fork_defense",
        "outcome": "success",
        "threats": [witness],
        "played": played,
        "best": None,
        "boundary": "positional opponent-turn prefilter, then a legal alternative and bounded fork proof using actual history",
    }
