"""Find a distinct legal positional witness for the same discovered mate."""

import time

from .discovery_defense_mate import mating
from .fork_defense_safety import quiet_after

MAX_MOVES = 64
KEYS = ("move", "slider", "moved_from", "moved_to", "target")


def witness(board, played, defense, threat, deadline):
    moves = list(board.legal_moves)
    if len(moves) > MAX_MOVES:
        return None
    for move in moves:
        if time.monotonic() >= deadline:
            return None
        if move in (played, defense):
            continue
        after = quiet_after(board, move)
        if after is None:
            continue
        try:
            attack = after.parse_uci(threat["move"])
        except ValueError:
            continue
        proof = _match(after, attack, threat, deadline)
        if proof:
            return {"move": move.uci(), "san": board.san(move), "proof": proof}
    return None


def _match(board, attack, threat, deadline):
    proof = next(
        (
            proof
            for proof in mating(board, attack)
            if all(proof[key] == threat[key] for key in KEYS)
        ),
        None,
    )
    return proof if time.monotonic() < deadline else None
