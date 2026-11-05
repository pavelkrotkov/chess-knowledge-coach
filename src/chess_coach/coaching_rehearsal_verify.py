"""Replay the single recorded move of an exact mate rehearsal."""

import json

import chess


def checkmate(fen, event):
    response = json.loads(event["response_json"])
    board = chess.Board(fen)
    move = chess.Move.from_uci(event["submitted_move"])
    if response.get("feedback") != "objective_verified" or move not in board.legal_moves:
        return False
    board.push(move)
    return board.is_checkmate() and response.get("fen") == board.fen()
