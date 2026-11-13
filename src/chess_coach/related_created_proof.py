"""Prove one same-role created material exposure and a supplied alternative."""

import chess

from .material_defense_guard import best_protects
from .material_defense_probe import candidate


def nominations(board, good, source):
    # Pseudo-captures only nominate; prove() checks the legal material consequence.
    moves = []
    for move in board.legal_moves:
        if not _matching_move(board, move, good, source):
            continue
        after = board.copy()
        after.push(move)
        for capture in after.generate_pseudo_legal_captures():
            attacker = after.piece_at(capture.from_square)
            if _matching_capture(attacker, capture, move, source):
                moves.append((move, capture))
    return sorted(moves, key=lambda pair: (pair[0].uci(), pair[1].uci()))


def _matching_move(board, move, good, source):
    piece = board.piece_at(move.from_square)
    delta = (
        abs(chess.square_file(move.to_square) - chess.square_file(move.from_square)),
        abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)),
    )
    return all(
        (
            piece is not None,
            piece and piece.piece_type == source["mover"],
            delta == source["geometry"],
            move != good,
            not board.is_capture(move),
            not board.gives_check(move),
            not move.promotion,
        )
    )


def _matching_capture(attacker, capture, move, source):
    return bool(
        capture.to_square == move.to_square and attacker and attacker.piece_type == source["target"]
    )


def prove(board, good, bad, capture):
    probe = candidate(board, bad.uci())
    if not probe or "outcome" in probe:
        return None
    if probe["before"]["targets"] or probe["before"]["uncertain"]:
        return None
    target = probe["target"]
    if capture.uci() not in probe["following"]["targets"].get(target, []):
        return None
    if not best_protects(board, probe, {"uci": [good.uci()]}):
        return None
    return {"good": good.uci(), "bad": bad.uci(), "capture": capture.uci()}
