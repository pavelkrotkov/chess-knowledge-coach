"""Exclude repetition, draw and promotion-sensitive continuation lines."""

import chess


def history_safe(board):
    return not board.is_repetition(2) and not board.is_game_over(claim_draw=True)


def lines_safe(board, lines):
    for line in lines:
        replay = board.copy()
        for uci in (line.get("pv") or "").split()[:4]:
            try:
                move = chess.Move.from_uci(uci)
                if move not in replay.legal_moves or move.promotion:
                    return False
                replay.push(move)
            except ValueError:
                return False
            if not history_safe(replay):
                return False
    return True
