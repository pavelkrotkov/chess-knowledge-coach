"""Read bounded PGN candidates and their explicitly supplied variations."""

import io

import chess.pgn

from .public_training_pgn_lex import valid_movetext
from .public_training_pgn_lines import pgn_lines


class QuietBuilder(chess.pgn.GameBuilder):
    def handle_error(self, error):
        self.game.errors.append(error)


def read_pgn(path):
    text = path.read_text(encoding="utf-8")
    with io.StringIO(text) as stream:
        for number in range(1, 5002):
            start = stream.tell()
            game = chess.pgn.read_game(stream, Visitor=QuietBuilder)
            raw = text[start : stream.tell()]
            if game is None:
                return
            if number > 5000:
                raise ValueError("collection record limit exceeded")
            if game.errors or not valid_movetext(raw):
                yield number, None, "malformed PGN"
                continue
            try:
                task = {
                    "id": game.headers.get("TaskId", ""),
                    "fen": game.board().fen(),
                    "objective": game.headers.get("Objective", ""),
                    "lines": pgn_lines(game),
                }
                yield number, task, None
            except (ValueError, TypeError):
                yield number, None, "invalid PGN position or lines"
