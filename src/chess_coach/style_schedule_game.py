"""Reconstruct one owned game into scheduling candidates."""

import io

import chess
import chess.pgn

from .analysis_positions import decisions
from .style_history_lines import history_safe

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


def _candidate(position, board):
    move = chess.Move.from_uci(position["uci"])
    if not history_safe(board) or move.promotion:
        detail = "history_or_promotion_unsupported"
    elif board.legal_moves.count() <= 1:
        detail = "forced_move"
    else:
        detail = "eligible"
    return {
        "game_id": position["game_id"],
        "position_id": position["id"],
        "in_check": board.is_check(),
        "status": "ready" if detail == "eligible" else "unknown",
        "detail": detail,
    }
