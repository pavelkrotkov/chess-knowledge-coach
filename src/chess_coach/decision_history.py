"""Reconstruct and validate the original game history for a decision."""

from .analysis_positions import decisions


def decision_board(db, position):
    game = db.connection.execute(
        "SELECT * FROM games WHERE id=?", (position["game_id"],)
    ).fetchone()
    for row, board in decisions(db.connection, game):
        if row["id"] == position["id"]:
            return board
    raise ValueError("decision is not in game history")
