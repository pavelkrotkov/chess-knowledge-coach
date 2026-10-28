"""Conservative matching of a runtime learner to a game side."""

from __future__ import annotations

import io
import sqlite3

import chess.pgn

UNKNOWN = {"", "?", "-", "default"}


def normalize_identity(value: str | None) -> str | None:
    normalized = value.strip().casefold() if value else ""
    return None if normalized in UNKNOWN else normalized


def learner_color(game: sqlite3.Row, learner: str | None) -> str | None:
    subject = normalize_identity(learner)
    if subject is None or not recorded_players_match(game):
        return None
    matches = [color for color in ("white", "black") if normalize_identity(game[color]) == subject]
    return matches[0] if len(matches) == 1 else None


def recorded_players_match(game: sqlite3.Row) -> bool:
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    if headers is None:
        return False
    return all(
        normalize_identity(game[color]) == normalize_identity(headers.get(color.title()))
        for color in ("white", "black")
    )
