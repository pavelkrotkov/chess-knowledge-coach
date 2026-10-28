"""Parse a PGN without logging player headers on errors."""

import io

import chess.pgn


class QuietGameBuilder(chess.pgn.GameBuilder):
    def handle_error(self, error: Exception) -> None:
        self.game.errors.append(error)


def parse_game(raw: str) -> chess.pgn.Game | None:
    return chess.pgn.read_game(io.StringIO(raw), Visitor=QuietGameBuilder)
