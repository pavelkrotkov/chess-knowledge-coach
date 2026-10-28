"""Atomic PGN ingestion; raw games are immutable."""

from __future__ import annotations

import io
from typing import TextIO, cast

import chess.pgn

from .db import Database
from .ingest_game import insert_game
from .ingest_reader import RecordingReader, SilentGameBuilder
from .ingest_syntax import validate_syntax
from .ingest_validation import raw_game, validate_game


def ingest_pgn(
    db: Database,
    pgn: str | TextIO,
    source: str = "local",
    *,
    raw_pgn_override: str | None = None,
) -> dict[str, int]:
    if db.connection.in_transaction:
        raise RuntimeError("cannot ingest during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = ingest_in_transaction(db, pgn, source, raw_pgn_override=raw_pgn_override)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def ingest_in_transaction(
    db: Database,
    pgn: str | TextIO,
    source: str = "local",
    *,
    raw_pgn_override: str | None = None,
) -> dict[str, int]:
    source_stream = cast(TextIO, pgn) if hasattr(pgn, "read") else io.StringIO(pgn)
    stream = RecordingReader(source_stream)
    totals = {"games": 0, "positions": 0}
    seen = 0
    while game := chess.pgn.read_game(cast(TextIO, stream), Visitor=SilentGameBuilder):
        record = stream.take()
        validate_syntax(record)
        validate_game(game, source, record)
        seen += 1
        if raw_pgn_override is not None and seen > 1:
            raise ValueError("raw PGN override supports one game")
        raw = raw_game(game, raw_pgn_override)
        validate_game(game, source, raw)
        result = insert_game(db.connection, game, source, raw)
        for key in totals:
            totals[key] += result[key]
    validate_syntax(stream.take())
    if not seen:
        raise ValueError("no valid PGN game found")
    return totals
