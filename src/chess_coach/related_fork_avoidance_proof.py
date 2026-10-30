"""Select a proven created fork matching the particular source roles."""

import chess

from .related_fork_avoidance_roles import describe_choice, same_roles


def pick(board, good, bad, after, before, source, proofs):
    for proof in proofs:
        if _created(before, proof):
            features = _compatible(board, good, bad, after, proof, source)
            if features is not None:
                return {"bad_move": bad.uci(), "fork": proof}, features
    return None


def _created(before, proof):
    return before.get(proof["move"]) != [chess.parse_square(s) for s in proof["targets"]]


def _compatible(board, good, bad, after, proof, source):
    try:
        features = describe_choice(board, good, bad, after, proof)
        return features if same_roles(source, features) else None
    except (ValueError, TypeError, KeyError, IndexError):
        return None
