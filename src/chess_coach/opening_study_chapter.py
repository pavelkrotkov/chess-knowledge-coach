"""Preserve reviewed opening PGNs while adding private Study metadata."""

import io

import chess
import chess.pgn

from .course_guidance import chapter_title
from .ingest_reader import SilentGameBuilder
from .opening_storage import position_key


def chapter(value, color, fen, *, exact=True):
    game = chess.pgn.read_game(io.StringIO(value["pgn"]), Visitor=SilentGameBuilder)
    if game is None or game.errors:
        raise ValueError("opening chapter differs")
    if exact and game.board().fen() != fen:
        raise ValueError("opening chapter differs")
    if position_key(game.board()) != position_key(chess.Board(fen)):
        raise ValueError("opening chapter differs")
    if color != ("white" if game.board().turn else "black"):
        raise ValueError("opening orientation differs")
    return {
        **value,
        "title": chapter_title(value["title"], color, False),
        "orientation": color,
        "mode": "conceal",
    }, game


def line(game, moves):
    node = game
    for text in moves.split():
        move = chess.Move.from_uci(text)
        if not node.has_variation(move):
            return False
        node = node.variation(move)
    return not node.variations
