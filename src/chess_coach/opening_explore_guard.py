"""Bound selected source fields before the existing replay helpers load them."""

from .objective_source_budget import MAX_GAME_BYTES

MAX_FIELD_BYTES = 1024
MAX_FEN_BYTES = 200
MAX_MOVE_BYTES = 32
MAX_POSITIONS = 1000

GAME_FIELDS = (
    "source",
    "source_id",
    "event",
    "site",
    "date",
    "round",
    "white",
    "black",
    "result",
    "time_control",
    "variant",
    "termination",
)


def _too_long(column, limit):
    return f"length(substr(CAST({column} AS BLOB),1,{limit + 1}))>{limit}"


def require_bounded(db, game_id):
    game_tests = [_too_long("pgn", MAX_GAME_BYTES)]
    game_tests.extend(_too_long(column, MAX_FIELD_BYTES) for column in GAME_FIELDS)
    if db.connection.execute(
        "SELECT 1 FROM games WHERE id=? AND (" + " OR ".join(game_tests) + ")",
        (game_id,),
    ).fetchone():
        raise ValueError("opening game exceeds input limits")
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET ?", (game_id, MAX_POSITIONS)
    ).fetchone():
        raise ValueError("opening game exceeds position limit")
    tests = [
        _too_long("fen", MAX_FEN_BYTES),
        _too_long("san", MAX_MOVE_BYTES),
        _too_long("uci", MAX_MOVE_BYTES),
    ]
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? AND (" + " OR ".join(tests) + ") LIMIT 1",
        (game_id,),
    ).fetchone():
        raise ValueError("opening positions exceed input limits")
