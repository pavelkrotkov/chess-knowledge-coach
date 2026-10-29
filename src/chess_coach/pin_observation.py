"""Describe verified pin execution and preserve unsupported geometry as ambiguity."""

import chess

from .material_ambiguity import ambiguous
from .material_observation_fallback import _best_move
from .pin_geometry import pins
from .pin_proof import proven


def observe(board, played, best_line, played_line):
    try:
        actual = chess.Move.from_uci(played)
    except ValueError:
        return None
    if actual not in board.legal_moves:
        return None
    geometry = pins(board, actual)
    results = proven(board, actual)
    if results:
        return {"kind": results[0]["type"], "outcome": "success", "proof": results[0]}
    return _unresolved(board, actual, best_line, geometry)


def _unresolved(board, actual, best_line, geometry):
    best = _best_move(board, best_line)
    alternative = pins(board, best) if isinstance(best, chess.Move) else []
    if not geometry and not alternative:
        return None
    candidate = (geometry or alternative)[0]
    selected = actual if geometry else best
    fact = ambiguous(candidate["type"], "pin_consequence_or_alternative_unresolved")
    fact["geometry"] = {
        "move": selected.uci(),
        "san": board.san(selected),
        "origin": "played" if geometry else "engine_alternative",
        "pinned": chess.square_name(candidate["pinned"]),
        "rear": chess.square_name(candidate["rear"]),
    }
    return fact
