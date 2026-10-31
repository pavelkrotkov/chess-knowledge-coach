"""Build and validate one annotated PGN chapter."""

import io

import chess
import chess.pgn

from .ingest_reader import SilentGameBuilder


def chapter(title, note, snapshot, provenance):
    board = chess.Board(snapshot["prompt_fen"])
    if not board.is_valid():
        raise ValueError("invalid practice starting position")
    if snapshot["learner_color"] != ("white" if board.turn else "black"):
        raise ValueError("invalid practice starting position")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["Event"] = title
    game.headers["White"] = "White"
    game.headers["Black"] = "Black"
    game.comment = note
    for line in snapshot["lines"]:
        _add_line(game, board, line)
    if not game.variations:
        raise ValueError("practice continuation unavailable")
    pgn = str(game)
    _validate(pgn, board.fen())
    return {
        "title": title,
        "orientation": snapshot["learner_color"],
        "pgn": pgn,
        "source": provenance,
        "source_snapshot": snapshot,
    }


def _add_line(game, board, line):
    current = board.copy()
    node = game
    for move_text in line.split():
        move = current.parse_uci(move_text)
        if move not in current.legal_moves:
            raise ValueError("invalid practice continuation")
        node = node.variation(move) if node.has_variation(move) else node.add_variation(move)
        current.push(move)


def _validate(pgn, fen):
    parsed = chess.pgn.read_game(io.StringIO(pgn), Visitor=SilentGameBuilder)
    if parsed is None or parsed.errors or parsed.board().fen() != fen:
        raise ValueError("course PGN validation failed")
