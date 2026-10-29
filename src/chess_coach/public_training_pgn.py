"""Read bounded PGN candidates and their explicitly supplied variations."""

import chess.pgn


class QuietBuilder(chess.pgn.GameBuilder):
    def handle_error(self, error):
        self.game.errors.append(error)


def read_pgn(path):
    with path.open(encoding="utf-8") as stream:
        for number in range(1, 5002):
            game = chess.pgn.read_game(stream, Visitor=QuietBuilder)
            if game is None:
                return
            if number > 5000:
                raise ValueError("collection record limit exceeded")
            if game.errors:
                yield number, None, "malformed PGN"
                continue
            try:
                task = {
                    "id": game.headers.get("TaskId", ""),
                    "fen": game.board().fen(),
                    "objective": game.headers.get("Objective", ""),
                    "lines": _lines(game),
                }
                yield number, task, None
            except (ValueError, TypeError):
                yield number, None, "invalid PGN position or lines"


def _lines(game):
    stack = [(game, [])]
    lines = []
    while stack:
        node, moves = stack.pop()
        if not node.variations:
            lines.append(" ".join(moves))
            if len(lines) > 16:
                raise ValueError("too many PGN lines")
        for child in reversed(node.variations):
            if len(moves) >= 64:
                raise ValueError("PGN line too long")
            stack.append((child, [*moves, child.move.uci()]))
    return lines
