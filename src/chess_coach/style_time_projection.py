"""Versioned derived game-start and ownership metadata; raw games remain authoritative."""

import re

from .learner_identity import normalize_identity, recorded_players_match
from .learner_time import observation_time

VERSION = "utc-game-start-v1"


def unique_tags(pgn, names):
    tags = re.findall(r"(?m)^\s*\[(UTCDate|UTCTime|White|Black)\s+", pgn)
    return all(tags.count(name) == 1 for name in names)


def identities(game):
    if not all(isinstance(game[key], str) for key in ("pgn", "white", "black")):
        return None
    white = normalize_identity(game["white"])
    black = normalize_identity(game["black"])
    if not white or not black or white == black or not recorded_players_match(game):
        return None
    if not unique_tags(game["pgn"], ("White", "Black")):
        return None
    return white, black


def projection(game):
    players = identities(game)
    if players is None:
        return (VERSION, "unknown_identity", None, None, None)
    started = (
        observation_time(game["pgn"]) if unique_tags(game["pgn"], ("UTCDate", "UTCTime")) else None
    )
    return (VERSION, "current" if started else "unknown_time", started, *players)


def update_projection(connection, game_id):
    game = connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    values = projection(game)
    connection.execute(
        """UPDATE style_game_times SET version=?, status=?, started_at=?, white_identity=?,
        black_identity=? WHERE game_id=?""",
        (*values, game_id),
    )
