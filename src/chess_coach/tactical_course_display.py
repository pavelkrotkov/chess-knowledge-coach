"""Render a bounded legal line from one immutable prepared chapter."""

import io

import chess
import chess.pgn

from .ingest_reader import SilentGameBuilder
from .web_board import board_rows
from .web_practice_reveal import _positions


def _note(chapter, board):
    game = chess.pgn.read_game(io.StringIO(chapter["pgn"]), Visitor=SilentGameBuilder)
    if game is None or game.errors or game.board().fen() != board.fen():
        raise ValueError("prepared chapter unavailable")
    color = chapter["orientation"].capitalize()
    prefix = f"Worked example, ungraded. You follow {color}'s recorded line. "
    suffix = (
        "Use the move controls to step through the recorded line; other moves are not "
        "judged here. Preview is used for the interactive chapters."
    )
    return game.comment.removeprefix(prefix).removesuffix(suffix).strip()


def chapter(chapter, index, line):
    snapshot = chapter["source_snapshot"]
    board = chess.Board(snapshot["prompt_fen"])
    color = chapter["orientation"]
    if not board.is_valid() or color != ("white" if board.turn else "black"):
        raise ValueError("prepared position unavailable")
    lines = snapshot["lines"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 64:
        raise ValueError("prepared lines unavailable")
    moves = _positions(board.fen(), lines[line].split(), color)
    return {
        "chapter": chapter,
        "index": index,
        "line": line,
        "line_count": len(lines),
        "board": board_rows(board.fen(), color),
        "moves": moves,
        "note": _note(chapter, board),
    }
