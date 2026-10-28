"""Validate complete PGN records from the Lichess export stream."""

from __future__ import annotations

import re

from .lichess_game import parse_game
from .lichess_support import headers, supported


def parse_page(payload: str) -> list[str]:
    text = payload.strip()
    if not text:
        return []
    if not text.startswith("[Event "):
        raise ValueError("malformed or truncated Lichess export")
    records = re.split("(?m)(?=^" + re.escape("[Event ") + ")", text)
    return [validate_record(record) for record in records if record.strip()]


def validate_record(record: str) -> str:
    raw = record.strip() + chr(10)
    if '[Result "' not in raw:
        raise ValueError("missing Lichess game result")
    tags = headers(raw)
    result = tags.get("Result")
    if result not in {"1-0", "0-1", "1/2-1/2", "*"} or not raw.rstrip().endswith(result):
        raise ValueError("truncated or invalid Lichess game export")
    if not supported(raw):
        return raw
    from .ingest_syntax import validate_syntax

    validate_syntax(raw)
    game = parse_game(raw)
    if game is None or game.errors:
        raise ValueError("invalid Lichess game PGN")
    return raw
