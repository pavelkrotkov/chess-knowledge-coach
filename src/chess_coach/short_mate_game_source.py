"""Load and recheck one dated, attributable game without holding a proof lock."""

from .learner_identity import normalize_identity
from .mate_game_sample import prepared_game
from .pipeline_inputs import game_input
from .recurrence_snapshot import read_snapshot
from .style_time_candidates import verified
from .style_time_query import load_game


def prepare(db, learner, game_id):
    subject = normalize_identity(learner)
    if not subject:
        raise ValueError("learner unavailable")
    with read_snapshot(db):
        game = _game(db, subject, game_id)
        identity, pairs = prepared_game(db, game, subject)
        signature = _signature(db, game)
        return {
            "game_id": game_id,
            "started_at": game["projected_start"],
            "identity": identity,
            "signature": signature,
            "pairs": pairs,
        }


def recheck(db, learner, source):
    subject = normalize_identity(learner)
    with read_snapshot(db):
        game = _game(db, subject, source["game_id"])
        if _signature(db, game) != source["signature"]:
            raise ValueError("game changed during inspection")


def _game(db, subject, game_id):
    game = load_game(db.connection, game_id)
    if game is None or verified(game, subject) is None:
        raise ValueError("game unavailable")
    return game


def _signature(db, game):
    return (
        game_input(db, game["id"]),
        game["result"],
        game["projected_start"],
        game["projected_white"],
        game["projected_black"],
    )
