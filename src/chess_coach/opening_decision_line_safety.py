"""Check complete candidate variations against the original game history."""

import chess

from .style_history_lines import history_safe

MAX_PLIES = 100


def _line_safe(board, line):
    moves = (line.get("pv") or "").split()
    if not 0 < len(moves) <= MAX_PLIES:
        return False
    replay = board.copy()
    for text in moves:
        try:
            move = chess.Move.from_uci(text)
            if move not in replay.legal_moves or move.promotion:
                return False
            replay.push(move)
        except ValueError:
            return False
        if not history_safe(replay):
            return False
    return True


def lines_safe(board, lines):
    return all(_line_safe(board, line) for line in lines)
