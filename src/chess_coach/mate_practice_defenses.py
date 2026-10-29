"""Validate all defensive replies and their mating witnesses."""

import chess


def defense_lines(board, root, move):
    if root["distance_plies"] != 3 or board.outcome(claim_draw=False) or board.can_claim_draw():
        raise ValueError("invalid mate proof")
    defenses = root["defenses"]
    if {item["defense"]["uci"] for item in defenses} != {
        reply.uci() for reply in board.legal_moves
    }:
        raise ValueError("incomplete defenses")
    return [_line(board, move, item) for item in defenses]


def _line(board, move, item):
    reply = chess.Move.from_uci(item["defense"]["uci"])
    board.push(reply)
    try:
        mate = chess.Move.from_uci(item["mate"]["uci"])
        if board.outcome(claim_draw=False) or mate not in board.legal_moves:
            raise ValueError("invalid mate proof")
        board.push(mate)
        try:
            if not board.is_checkmate():
                raise ValueError("invalid mate proof")
        finally:
            board.pop()
        return " ".join((move.uci(), reply.uci(), mate.uci()))
    finally:
        board.pop()
