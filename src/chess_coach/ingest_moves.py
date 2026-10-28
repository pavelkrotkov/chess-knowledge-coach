"""Persist post-move boards and clocks for an imported game."""

from __future__ import annotations

import re
import sqlite3

import chess.pgn

CLOCK_RE = re.compile(r"\[%clk\s+(?P<clock>[0-9:.]+)\]")


def _clock_seconds(value: str) -> float:
    parts = [float(part) for part in value.split(":")]
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    return parts[0]


def store_positions(connection: sqlite3.Connection, game_id: int, game: chess.pgn.Game) -> int:
    board = game.board()
    count = 0
    for ply, node in enumerate(game.mainline(), start=1):
        match = CLOCK_RE.search(node.comment)
        clock = _clock_seconds(match.group("clock")) if match else None
        move = node.move
        san = board.san(move)
        board.push(move)
        connection.execute(
            "INSERT INTO positions (game_id, ply, fen, san, uci, clock_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (game_id, ply, board.fen(), san, move.uci(), clock),
        )
        count += 1
    return count
