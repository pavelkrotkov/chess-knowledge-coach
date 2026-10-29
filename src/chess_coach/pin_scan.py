"""Bound pin candidate discovery and proof without guessing unexamined defenses."""

from .material_exchange_rules import unclear
from .pin_geometry import pins
from .pin_proof import proof

MAX_MOVES = 64
MAX_PINS = 16


def scan(board):
    if unclear(board) or board.ep_square is not None:
        return None
    moves = list(board.legal_moves)
    if not moves or len(moves) > MAX_MOVES:
        return None
    candidates = [(move, pin) for move in moves for pin in pins(board, move)]
    if len(candidates) > MAX_PINS:
        move, pin = candidates[0]
        return {"proven": [], "uncertain": [{**pin, "move": move.uci(), "san": board.san(move)}]}
    return _classify(board, candidates)


def _classify(board, candidates):
    proven, uncertain = [], []
    for move, pin in candidates:
        witness = proof(board, move, pin)
        if witness:
            proven.append(witness)
        else:
            uncertain.append({**pin, "move": move.uci(), "san": board.san(move)})
    return {"proven": proven, "uncertain": uncertain}
