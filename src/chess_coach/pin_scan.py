"""Bound pin candidate discovery and proof without guessing unexamined defenses."""

from .material_exchange_rules import unclear
from .pin_geometry import pins
from .pin_proof import proof

MAX_MOVES = 64
MAX_PINS = 16


def scan(board, *, check=None, on_proof=None):
    tick = check or (lambda: None)
    tick()
    if unclear(board) or board.ep_square is not None:
        return None
    moves = list(board.legal_moves)
    if not 0 < len(moves) <= MAX_MOVES:
        return None
    candidates = []
    for move in moves:
        tick()
        candidates.extend((move, pin) for pin in pins(board, move))
    if len(candidates) > MAX_PINS:
        move, pin = candidates[0]
        return {
            "proven": [],
            "uncertain": [
                {
                    **pin,
                    "move": move.uci(),
                    "san": board.san(move),
                    "reason": "candidate_budget_exhausted",
                }
            ],
        }
    return _classify(board, candidates, check, on_proof)


def _classify(board, candidates, check, on_proof):
    proven, uncertain = [], []
    for move, pin in candidates:
        witness = proof(board, move, pin, check=check, on_proof=on_proof)
        if witness:
            proven.append(witness)
        else:
            uncertain.append({**pin, "move": move.uci(), "san": board.san(move)})
    return {"proven": proven, "uncertain": uncertain}
