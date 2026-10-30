"""Attribute and fingerprint a purpose diagnostic's owned game source."""

from .fact_fingerprint import canonical, digest
from .learner_identity import learner_color


def owned_game(db, game_id, learner):
    game = db.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        raise ValueError("game is unavailable")
    try:
        color = learner_color(game, learner)
    except (TypeError, ValueError):
        color = None
    if color is None:
        raise ValueError("learner is not attributable to this game")
    return game, color


def history_fingerprint(game, color, rows):
    return digest(
        canonical(
            {
                "pgn": game["pgn"],
                "white": game["white"],
                "black": game["black"],
                "variant": game["variant"],
                "color": color,
                "positions": [dict(row) for row in rows],
            }
        )
    )
