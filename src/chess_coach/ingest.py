from __future__ import annotations

import hashlib
import io
import re
from typing import TextIO, cast

import chess.pgn

from .db import Database

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


def ingest_pgn(db: Database, pgn: str | TextIO, source: str = "local") -> dict[str, int]:
    stream = cast(TextIO, pgn) if hasattr(pgn, "read") else io.StringIO(pgn)
    games = positions = 0
    while game := chess.pgn.read_game(stream):
        headers = game.headers
        raw_pgn = str(game)
        source_id = hashlib.sha256(raw_pgn.encode()).hexdigest()
        cur = db.connection.execute(
            """INSERT OR IGNORE INTO games
            (source, source_id, pgn, event, site, date, round, white, black,
             result, time_control, white_elo, black_elo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source,
                source_id,
                raw_pgn,
                headers.get("Event"),
                headers.get("Site"),
                headers.get("Date"),
                headers.get("Round"),
                headers.get("White", "?"),
                headers.get("Black", "?"),
                headers.get("Result", "*"),
                headers.get("TimeControl"),
                _int_or_none(headers.get("WhiteElo")),
                _int_or_none(headers.get("BlackElo")),
            ),
        )
        game_id = (
            cur.lastrowid
            or db.connection.execute(
                "SELECT id FROM games WHERE source = ? AND source_id = ?", (source, source_id)
            ).fetchone()[0]
        )
        board = game.board()
        for ply, node in enumerate(game.mainline(), start=1):
            clock = None
            match = CLOCK_RE.search(node.comment)
            if match:
                clock = _clock_seconds(match.group("clock"))
            move = node.move
            san = board.san(move)
            board.push(move)
            db.connection.execute(
                "INSERT OR IGNORE INTO positions (game_id, ply, fen, san, uci, clock_seconds) VALUES (?, ?, ?, ?, ?, ?)",
                (game_id, ply, board.fen(), san, move.uci(), clock),
            )
            positions += 1
        games += 1
    db.connection.commit()
    return {"games": games, "positions": positions}


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None
