"""Validate every prepared mating witness against original game history."""

import chess

from .mate_practice_defenses import defense_lines


def prepared_lines(board, proof):
    if not isinstance(proof, dict) or proof.get("version") != "mate-proof-v1":
        raise ValueError("mate proof unavailable")
    lines = []
    for root in proof["alternatives"]:
        if root["status"] == "proved":
            lines.extend(_root_lines(board, root))
    if not lines:
        raise ValueError("mate proof unavailable")
    return sorted(set(lines))


def _root_lines(board, root):
    move = chess.Move.from_uci(root["move"]["uci"])
    if move not in board.legal_moves:
        raise ValueError("invalid mate proof")
    board.push(move)
    try:
        if root["distance_plies"] == 1 and board.is_checkmate():
            return [move.uci()]
        return defense_lines(board, root, move)
    finally:
        board.pop()
