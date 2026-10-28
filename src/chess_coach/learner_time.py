"""Game-start time from explicit UTC PGN tags; unknown stays unknown."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import chess.pgn


def observation_time(pgn: str) -> str | None:
    headers = chess.pgn.read_headers(io.StringIO(pgn))
    if headers is None or not headers.get("UTCDate") or not headers.get("UTCTime"):
        return None
    try:
        value = datetime.strptime(f"{headers['UTCDate']} {headers['UTCTime']}", "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None
    return value.replace(tzinfo=UTC).isoformat()
