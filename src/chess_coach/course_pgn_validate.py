"""Verify a generated chapter starts at the intended legal board."""

import io

import chess.pgn

from .ingest_reader import SilentGameBuilder


def validate(pgn, fen):
    parsed = chess.pgn.read_game(io.StringIO(pgn), Visitor=SilentGameBuilder)
    if parsed is None or parsed.errors or parsed.board().fen() != fen:
        raise ValueError("course PGN validation failed")
