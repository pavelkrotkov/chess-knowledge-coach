"""Identify the same verified game across independent import routes."""

from .db import Database
from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity


def game_identity(db: Database, game_id: int, decisions: list[dict]) -> str:
    game = db.connection.execute(
        "SELECT white, black FROM games WHERE id = ?", (game_id,)
    ).fetchone()
    first = decisions[0]
    return digest(
        canonical(
            {
                "initial_position": first["prompt_fen"],
                "moves": [item["played_move"] for item in decisions],
                "white": normalize_identity(game["white"]),
                "black": normalize_identity(game["black"]),
                "observation_at": first["observation_at"],
            }
        )
    )
