"""Normalize coordinate or SAN input against the current server position."""

import re

import chess

_COORDINATE = re.compile(r"^[a-h][1-8][a-h][1-8]$")


def normalize_move(fen, text, promotion):
    text = text.strip()
    if promotion not in {"", "q", "r", "b", "n"}:
        raise ValueError("invalid promotion choice")
    if promotion and _COORDINATE.fullmatch(text):
        text += promotion
    try:
        board = chess.Board(fen)
        try:
            move = board.parse_uci(text)
        except ValueError:
            move = board.parse_san(text)
        return move.uci()
    except ValueError:
        return text
