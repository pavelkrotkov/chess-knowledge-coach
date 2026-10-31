"""Compare exported chapter moves and teaching comments after provider normalization."""

import io

import chess.pgn

from .ingest_reader import SilentGameBuilder
from .study_remote import StudyError


def chapters(text):
    result = []
    stream = io.StringIO(text)
    while game := chess.pgn.read_game(stream, Visitor=SilentGameBuilder):
        if game.errors:
            raise StudyError("Study export contains invalid PGN")
        result.append(game)
    return result


def matches(expected, exported):
    games = [
        game for game in chapters(exported) if game.headers.get("ChapterName") == expected["name"]
    ]
    if len(games) != 1:
        return False
    actual = games[0]
    original = chess.pgn.read_game(io.StringIO(expected["pgn"]), Visitor=SilentGameBuilder)
    if original is None or original.errors:
        return False
    return _same_position(expected, original, actual) and _moves(actual) == _moves(original)


def _text(value):
    return " ".join(value.split())


def _moves(node):
    return sorted(
        (child.move.uci(), _text(child.comment), _moves(child)) for child in node.variations
    )


def _same_position(expected, original, actual):
    return (
        actual.headers.get("Orientation", "").lower() == expected["orientation"]
        and actual.board().fen() == original.board().fen()
        and _text(actual.comment) == _text(original.comment)
    )
