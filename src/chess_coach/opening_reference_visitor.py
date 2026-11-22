"""Check a shared deadline while parsing bounded public PGN records."""

import chess.pgn

from .public_training_pgn import QuietBuilder


def timed(check):
    class TimedBuilder(QuietBuilder):
        def begin_game(self):
            check()
            return super().begin_game()

        def visit_header(self, tagname, tagvalue):
            check()
            return super().visit_header(tagname, tagvalue)

        def visit_move(self, board, move):
            check()
            return super().visit_move(board, move)

        def visit_comment(self, comment):
            check()
            return super().visit_comment(comment)

    return TimedBuilder


def read_game(stream, check):
    if check is None:
        return chess.pgn.read_game(stream, Visitor=QuietBuilder)
    check()
    game = chess.pgn.read_game(stream, Visitor=timed(check))
    check()
    return game
