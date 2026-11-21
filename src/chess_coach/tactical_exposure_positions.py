"""Extract only bounded, legal positions from provided tactical material."""

import chess

from .related_capture_position import prompt_key

MAX_POSITIONS = 4096
MAX_CHAPTERS = 64
MAX_TOTAL_POSITIONS = 8192


def position_key(board):
    if not board.is_valid():
        raise ValueError("tactical position unavailable")
    return prompt_key(board.fen())


def line_positions(chapter, line):
    snapshot = chapter["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    moves = snapshot["lines"][line].split()
    if len(moves) > MAX_POSITIONS:
        raise ValueError("tactical line exceeds exposure limit")
    result = {position_key(board)}
    for text in moves:
        board.push(board.parse_uci(text))
        result.add(position_key(board))
    return result
