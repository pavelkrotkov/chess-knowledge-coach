"""Inspect bounded position metadata; full replay remains authoritative."""

import chess

from .style_defense_nomination import distinct
from .style_early_center import eligible as early_center
from .style_schedule_clock import reached
from .style_schedule_game import MAX_POSITIONS, _standard


def _consistent(board, row):
    move = chess.Move.from_uci(row[3])
    if move.promotion or move not in board.legal_moves:
        raise ValueError("unsupported or illegal move")
    board.push(move)
    if row[5] is None or row[5] > 200 or board.fen() != row[4]:
        raise ValueError("stored move and position disagree")


def _checked_board(row, color, center):
    # The previous row stores the board after its move: this turn's start.
    fen, size = row[1], row[2]
    if fen is None or size > 200:
        raise ValueError("missing or oversized position")
    board = chess.Board(fen)
    if not board.is_valid() or board.turn != (color == "white"):
        raise ValueError("invalid position or turn")
    checked = board.is_check() and board.legal_moves.count() > 1
    structural = distinct(board, chess.Move.from_uci(row[3])) if checked else False
    early = early_center(board, row[0]) if center else False
    _consistent(board, row)
    return checked, structural, early


def _count(rows, color, center):
    checks = structural = unknown = checked = early = 0
    # Consecutive standard-start plies establish an advisory side to move.
    for expected, row in enumerate(rows, start=1):
        if reached() or row[0] != expected:
            raise ValueError("incomplete position metadata")
        if expected > 1 and expected % 2 == (color == "white"):
            is_check, different, nominated = _checked_board(row, color, center)
            if reached():
                raise ValueError("incomplete position metadata")
            checks += is_check
            structural += different is True
            unknown += different is None
            checked += 1
            early += nominated
    return checks, structural, unknown, checked, len(rows), early


def inspect(db, game, color, *, center=False):
    if game["variant"] != "Standard" or not _standard(game):
        raise ValueError("unsupported game")
    # ponytail: at most 1,001 rows per game; full replay validates provenance.
    rows = db.connection.execute(
        """SELECT p.ply, substr(prev.fen, 1, 201), length(prev.fen),
               substr(p.uci, 1, 6), substr(p.fen, 1, 201), length(p.fen)
        FROM positions p LEFT JOIN positions prev
          ON prev.game_id=p.game_id AND prev.ply=p.ply-1
        WHERE p.game_id=? ORDER BY p.ply LIMIT ?""",
        (game["id"], MAX_POSITIONS + 1),
    ).fetchall()
    if not rows or len(rows) > MAX_POSITIONS:
        raise ValueError("unsupported position count")
    return _count(rows, color, center)
