"""Inspect bounded position metadata; full replay remains authoritative."""

import chess

from .style_schedule_clock import reached
from .style_schedule_game import MAX_POSITIONS, _standard


def _checked_board(row, color):
    # The previous row stores the board after its move: this turn's start.
    fen, size = row[1], row[2]
    if fen is None or size > 200:
        raise ValueError("missing or oversized position")
    board = chess.Board(fen)
    if not board.is_valid() or board.turn != (color == "white"):
        raise ValueError("invalid position or turn")
    return board.is_check() and board.legal_moves.count() > 1


def _count(rows, color):
    checks = checked = 0
    # Consecutive standard-start plies establish an advisory side to move.
    for expected, row in enumerate(rows, start=1):
        if reached() or row[0] != expected:
            raise ValueError("incomplete position metadata")
        if expected > 1 and expected % 2 == (color == "white"):
            checks += _checked_board(row, color)
            checked += 1
    return checks, checked, len(rows)


def inspect(db, game, color):
    if game["variant"] != "Standard" or not _standard(game):
        raise ValueError("unsupported game")
    # ponytail: at most 1,001 rows per game; full replay validates provenance.
    rows = db.connection.execute(
        """SELECT p.ply, substr(prev.fen, 1, 201), length(prev.fen)
        FROM positions p LEFT JOIN positions prev
          ON prev.game_id=p.game_id AND prev.ply=p.ply-1
        WHERE p.game_id=? ORDER BY p.ply LIMIT ?""",
        (game["id"], MAX_POSITIONS + 1),
    ).fetchall()
    if not rows or len(rows) > MAX_POSITIONS:
        raise ValueError("unsupported position count")
    return _count(rows, color)
