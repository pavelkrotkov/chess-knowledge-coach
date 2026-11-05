"""Require the verified tactical mainline as well as normalized PGN content."""

import io

import chess.pgn

from .ingest_reader import SilentGameBuilder
from .study_pgn_verify import chapters, matches


def _mainline(game):
    return [node.move.uci() for node in game.mainline()]


def matches_mainline(expected, exported):
    if not matches(expected, exported):
        return False
    games = [
        game for game in chapters(exported) if game.headers.get("ChapterName") == expected["name"]
    ]
    original = chess.pgn.read_game(io.StringIO(expected["pgn"]), Visitor=SilentGameBuilder)
    return original is not None and len(games) == 1 and _mainline(original) == _mainline(games[0])
