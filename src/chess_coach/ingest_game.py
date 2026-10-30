"""Insert one immutable game or verify an identical replay."""

from __future__ import annotations

import sqlite3

import chess.pgn

from .ingest_identity import source_id
from .ingest_moves import store_positions
from .style_time_projection import update_projection
from .style_time_schema import ingest_projection_available


def integer(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def insert_game(
    connection: sqlite3.Connection, game: chess.pgn.Game, source: str, raw: str
) -> dict[str, int]:
    headers = game.headers
    identity = source_id(game, source, raw)
    has_projection = ingest_projection_available(connection)
    existing = connection.execute(
        "SELECT id, pgn FROM games WHERE source = ? AND source_id = ?", (source, identity)
    ).fetchone()
    if existing is not None:
        if existing["pgn"] != raw:
            raise ValueError("conflicting PGN for an existing game ID")
        return {"games": 0, "positions": 0}
    cursor = connection.execute(
        """INSERT INTO games
        (source, source_id, pgn, event, site, date, round, white, black, result, time_control,
         white_elo, black_elo, variant, termination)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source,
            identity,
            raw,
            headers.get("Event"),
            headers.get("Site"),
            headers.get("Date"),
            headers.get("Round"),
            headers.get("White", "?"),
            headers.get("Black", "?"),
            headers.get("Result", "*"),
            headers.get("TimeControl"),
            integer(headers.get("WhiteElo")),
            integer(headers.get("BlackElo")),
            headers.get("Variant", "Standard"),
            headers.get("Termination"),
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return the game ID")
    if has_projection:
        update_projection(connection, cursor.lastrowid)
    return {"games": 1, "positions": store_positions(connection, cursor.lastrowid, game)}
