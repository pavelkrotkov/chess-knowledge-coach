"""Parse a PGN without logging player headers on errors."""

import io

import chess.pgn

from .ingest_reader import SilentGameBuilder


def parse_game(raw: str) -> chess.pgn.Game | None:
    return chess.pgn.read_game(io.StringIO(raw), Visitor=SilentGameBuilder)
