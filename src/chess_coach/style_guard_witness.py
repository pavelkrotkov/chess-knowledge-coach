"""Prove a newly legal moved-piece recapture witness."""

import chess

from .material_exchange_rules import ordinary_capture
from .material_exchange_tree import recaptures
from .material_values import VALUES


def guard(board, after, move, square, named, options, budget, check):
    if move.from_square == square:
        return None
    attack = next((candidate for candidate in options if candidate.uci() == named), None)
    if attack is None or not _new_reply(board, after, move, square, attack):
        return None
    return _bound(after, move.to_square, square, attack, budget, check)


def reply_witness(after, square, attack, budget, check):
    board = after.copy(stack=True)
    board.push(attack)
    for reply in board.legal_moves:
        if reply.to_square == square and board.is_capture(reply):
            witness = _bound(after, reply.from_square, square, attack, budget, check)
            if witness is not None:
                return witness
    raise ValueError("recapture witness unavailable")


def _bound(after, origin, square, attack, budget, check):
    target, attacker = after.piece_at(square), after.piece_at(attack.from_square)
    if target is None or attacker is None:
        return None
    target_value = VALUES.get(target.piece_type)
    attacker_value = VALUES.get(attacker.piece_type)
    if target_value is None or attacker_value is None:
        return None
    reply_board = after.copy(stack=True)
    reply_board.push(attack)
    reply = chess.Move(origin, square)
    if not ordinary_capture(reply_board, reply):
        return None
    reply_board.push(reply)
    gain = recaptures(
        reply_board, square, after.turn, target_value - attacker_value, budget, 2, check
    )
    if gain is None:
        raise ValueError("guard exchange unresolved")
    if gain > 0:
        return None
    return {"capture": attack.uci(), "recapture": reply.uci(), "opponent_gain_max": gain}


def _new_reply(board, after, move, square, attack):
    # Compare legal recaptures after the same original capture on each board.
    old = board.copy(stack=False)
    old.turn = not old.turn
    if attack not in old.legal_moves:
        return False
    old.push(attack)
    if chess.Move(move.from_square, square) in old.legal_moves:
        return False
    fresh = after.copy(stack=True)
    fresh.push(attack)
    return chess.Move(move.to_square, square) in fresh.legal_moves
