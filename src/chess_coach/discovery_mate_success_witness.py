"""Prove nominated discovered mate after a distinct legal quiet alternative."""

from .discovery_defense_mate import mating
from .discovery_defense_witness import KEYS
from .fork_defense_safety import quiet_after

MAX_MOVES = 64


def witness(board, played, candidates, check):
    moves = list(board.legal_moves)
    if len(moves) > MAX_MOVES:
        return None, "witness_move_limit"
    for move in sorted(moves, key=lambda item: item.uci()):
        check()
        if move == played:
            continue
        after = quiet_after(board, move)
        if after is None:
            continue
        found = _after(board, after, move, candidates, check)
        if found:
            return found, None
    return None, "witness_unavailable"


def _after(board, after, move, candidates, check):
    for candidate in candidates:
        check()
        try:
            attack = after.parse_uci(candidate["move"])
        except ValueError:
            continue
        for proof in mating(after, attack):
            check()
            if all(proof[key] == candidate[key] for key in KEYS):
                return {
                    "move": move.uci(),
                    "san": board.san(move),
                    "proof": proof,
                    "nomination": candidate,
                }
    return None
