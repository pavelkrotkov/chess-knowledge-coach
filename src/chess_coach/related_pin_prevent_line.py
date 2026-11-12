"""Prove a same-kind pinner capture and replay the complete supplied line."""

import chess

from .material_lines import material
from .pin_capture import capture
from .puzzle_session_validate import legal_move
from .related_pin_budget import take
from .related_pin_prevent_nominate import nominate
from .related_pin_prevent_shape import features


def candidate_line(board, line, source, budget):
    try:
        candidate = nominate(board, line, source)
        if candidate is None or not take(budget, "lines") or not take(budget, "root_proofs"):
            return None
        move, attacker, pin = candidate
        _replay(board, line)
        if not capture(board, move.from_square, attacker, board.turn, material(board, board.turn)):
            return None
        shape = features(board, move, attacker, pin)
        proof = {
            "kind": pin["type"],
            "pinner": chess.square_name(attacker),
            "pinned": chess.square_name(pin["pinned"]),
            "rear": chess.square_name(pin["rear"]),
        }
        return shape, proof, {"move": move.uci(), "san": board.san(move)}
    except (ValueError, TypeError, KeyError, IndexError):
        budget["unknown"] += 1
        return None


def _replay(board, line):
    replay = board.copy(stack=True)
    for text in line:
        if replay.is_game_over(claim_draw=True):
            raise ValueError("pin line ended")
        replay.push(legal_move(replay, text))
