"""Recover a prior canonical game identity from bounded stored metadata."""

from .style_schedule_game import MAX_POSITIONS, _standard
from .style_schedule_identity import identity
from .style_time_candidates import verified
from .style_time_query import load_game


def resolve(db, game_id):
    game = load_game(db.connection, game_id)
    if game is None or not verified(game, game["projected_white"]):
        raise ValueError("prior game projection is unavailable")
    if game["variant"] != "Standard" or not _standard(game):
        raise ValueError("prior game history is unavailable")
    return identity(db, game, _rows(db, game_id))


def _rows(db, game_id):
    rows = db.connection.execute(
        """SELECT ply,NULL,NULL,substr(uci,1,6) FROM positions
        WHERE game_id=? ORDER BY ply LIMIT ?""",
        (game_id, MAX_POSITIONS + 1),
    ).fetchall()
    if not rows or len(rows) > MAX_POSITIONS:
        raise ValueError("prior game history is unavailable")
    if any(row[0] != index for index, row in enumerate(rows, 1)):
        raise ValueError("prior game history is incomplete")
    return rows
