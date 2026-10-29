"""Verify immediate pawn recaptures after legal attacks on a supported piece."""

import chess


def _reply(board, pawn_square, target_square, capture):
    replay = board.copy()
    replay.push(replay.parse_san(capture["san"]))
    reply = chess.Move(pawn_square, target_square)
    if reply in replay.legal_moves and replay.is_capture(reply):
        return {"capture": capture["san"], "reply": replay.san(reply)}
    return None


def recaptures(board, pawn_square, target_square, check):
    if pawn_square is None or check["status"] != "checked":
        return []
    pawn = board.piece_at(pawn_square)
    if pawn is None or pawn.piece_type != chess.PAWN or pawn.color == board.turn:
        return []
    return [
        reply
        for capture in check["captures"]
        if (reply := _reply(board, pawn_square, target_square, capture))
    ]
