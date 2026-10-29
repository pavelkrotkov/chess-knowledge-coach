"""Find legal captures of the pinner with bounded material verification."""

from .material_lines import material
from .pin_capture import capture


def capture_defenses(board, candidates):
    initial = material(board, board.turn)
    attackers = {attacker for attacker, _ in candidates}
    return [
        {"move": move.uci(), "san": board.san(move)}
        for move in board.legal_moves
        if move.to_square in attackers
        and capture(board, move.from_square, move.to_square, board.turn, initial)
    ]
