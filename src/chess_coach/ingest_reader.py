"""Capture each parsed PGN record without loading the whole input."""

from __future__ import annotations

from typing import TextIO

import chess.pgn


class RecordingReader:
    def __init__(self, source: TextIO) -> None:
        self.source = source
        self.lines: list[str] = []

    def readline(self) -> str:
        line = self.source.readline()
        self.lines.append(line)
        return line

    def take(self) -> str:
        result = "".join(self.lines)
        self.lines.clear()
        return result


class SilentGameBuilder(chess.pgn.GameBuilder):
    """Record parser errors without logging game headers."""

    def handle_error(self, error: Exception) -> None:
        self.game.errors.append(error)
