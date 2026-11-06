"""Reconstruct one owned game into scheduling candidates."""

import io

import chess
import chess.pgn

from .analysis_positions import decisions
from .style_schedule_candidate import candidate as _candidate

MAX_POSITIONS = 1000


def _standard(game):
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    return headers is not None and "FEN" not in headers and headers.get("SetUp") != "1"


def game_candidates(db, game, color):
    count = db.connection.execute(
        "SELECT COUNT(*) FROM positions WHERE game_id=?", (game["id"],)
    ).fetchone()[0]
    if count > MAX_POSITIONS or not _standard(game):
        raise ValueError("unsupported_history")
    rows = []
    for position, board in decisions(db.connection, game):
        if ("white" if board.turn == chess.WHITE else "black") != color:
            continue
        rows.append(_candidate(position, board))
    return rows
