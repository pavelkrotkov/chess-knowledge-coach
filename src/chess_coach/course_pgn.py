"""Build and validate one annotated PGN chapter."""

import chess
import chess.pgn

from .course_guidance import chapter_title, prompt
from .course_pgn_validate import validate


def chapter(title, note, snapshot, provenance, *, gamebook=False, guidance=None):
    board = chess.Board(snapshot["prompt_fen"])
    if not board.is_valid() or snapshot["learner_color"] != ("white" if board.turn else "black"):
        raise ValueError("invalid practice starting position")
    title = chapter_title(title, snapshot["learner_color"], gamebook)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["Event"] = title
    game.headers["White"] = "White"
    game.headers["Black"] = "Black"
    game.comment = _guidance(note, snapshot["learner_color"], gamebook, guidance)
    for line in snapshot["lines"]:
        _add_line(game, board, line, gamebook)
    if not game.variations:
        raise ValueError("practice continuation unavailable")
    pgn = str(game)
    validate(pgn, board.fen())
    return {
        "title": title,
        "mode": "gamebook" if gamebook else "conceal",
        "orientation": snapshot["learner_color"],
        "pgn": pgn,
        "source": provenance,
        "source_snapshot": snapshot,
    }


def _guidance(note, color, gamebook, guidance):
    return prompt(note, color, gamebook) if guidance is None else guidance


def _add_line(game, board, line, gamebook):
    current = board.copy()
    node = game
    for move_text in line.split():
        move = current.parse_uci(move_text)
        node = node.variation(move) if node.has_variation(move) else node.add_variation(move)
        current.push(move)
    if gamebook:
        node.comment = "Correct. Exercise complete."
