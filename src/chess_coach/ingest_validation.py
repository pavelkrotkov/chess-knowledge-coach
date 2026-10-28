"""Validate parsed games and any raw PGN override before persistence."""

from __future__ import annotations

import io

import chess.pgn

from .ingest_syntax import validate_syntax


def raw_game(game: chess.pgn.Game, override: str | None) -> str:
    if override is None:
        return str(game)
    validate_syntax(override)
    stream = io.StringIO(override)
    original = chess.pgn.read_game(stream)
    if original is None or original.errors or str(original) != str(game):
        raise ValueError("raw PGN override does not match the parsed game")
    if chess.pgn.read_game(stream) is not None:
        raise ValueError("raw PGN override supports one game")
    return override


def validate_game(game: chess.pgn.Game, source: str, raw: str) -> None:
    if game.errors:
        raise ValueError("invalid PGN: parser reported errors")
    if source != "lichess":
        return
    result = game.headers.get("Result")
    if game.headers.get("Variant", "Standard") != "Standard" or result not in {
        "1-0",
        "0-1",
        "1/2-1/2",
    }:
        raise ValueError("unsupported or unfinished Lichess game")
    if not raw.rstrip().endswith(result):
        raise ValueError("incomplete Lichess game PGN")
