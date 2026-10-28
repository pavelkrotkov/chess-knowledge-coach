"""Stable identities for imported games."""

import hashlib
import re

import chess.pgn


def source_id(game: chess.pgn.Game, source: str, raw: str) -> str:
    game_id = game.headers.get("GameId") if source == "lichess" else None
    if source == "lichess" and not game_id:
        match = re.search(r"lichess[.]org/([A-Za-z0-9]{6,})", game.headers.get("Site", ""))
        game_id = match.group(1) if match else None
    if source == "lichess" and not game_id:
        raise ValueError("Lichess game has no stable ID")
    return game_id or hashlib.sha256(raw.encode()).hexdigest()
