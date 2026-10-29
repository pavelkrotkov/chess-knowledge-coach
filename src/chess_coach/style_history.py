"""Recheck selected decisions against their verified original game history."""

import io

import chess.pgn

from .analysis_positions import decisions


def selected_boards(db, game_id, position_ids):
    if not position_ids:
        return {}
    game = db.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    if headers is None or "FEN" in headers or headers.get("SetUp") == "1":
        return {}
    try:
        return {
            row["id"]: board
            for row, board in decisions(db.connection, game)
            if row["id"] in position_ids
        }
    except (ValueError, TypeError, IndexError):
        return {}
