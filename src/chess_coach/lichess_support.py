"""Read export headers and identify supported completed games."""

from __future__ import annotations

import io

import chess.pgn


def headers(raw: str) -> chess.pgn.Headers:
    result = chess.pgn.read_headers(io.StringIO(raw))
    if result is None:
        raise ValueError("invalid Lichess PGN headers")
    return result


def supported(raw: str) -> bool:
    tags = headers(raw)
    return tags.get("Variant", "Standard") == "Standard" and tags.get("Result") in {
        "1-0",
        "0-1",
        "1/2-1/2",
    }
