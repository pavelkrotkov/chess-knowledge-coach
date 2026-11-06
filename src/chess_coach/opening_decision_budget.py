"""Bound the input rereads for one opening decision."""

from .objective_source_budget import MAX_GAME_BYTES
from .opening_classification import CLASSIFIER_VERSION
from .opening_snapshot import SOURCE, VERSION
from .repertoire_game import _opening, _stale

MAX_POSITIONS = 1000
MAX_NODES = 10000
MAX_EDGES = 100000


def bounded(db, game_id, dataset_id):
    game = db.connection.execute(
        "SELECT length(CAST(pgn AS BLOB)) FROM games WHERE id=?", (game_id,)
    ).fetchone()
    if game is None or game[0] > MAX_GAME_BYTES:
        raise ValueError("game is unavailable")
    checks = (
        ("positions", "game_id", game_id, MAX_POSITIONS),
        ("opening_nodes", "dataset_id", dataset_id, MAX_NODES),
        ("opening_edges", "dataset_id", dataset_id, MAX_EDGES),
    )
    for table, key, value, limit in checks:
        if db.connection.execute(
            f"SELECT 1 FROM {table} WHERE {key}=? LIMIT 1 OFFSET ?", (value, limit)
        ).fetchone():
            raise ValueError("source exceeds the inspection limit")


def classification(db, game_id):
    opening = _opening(db, game_id)
    if opening is None:
        raise ValueError("current pinned opening classification unavailable")
    identity = (
        opening["version"],
        opening["source_url"],
        opening["classifier_version"],
        opening["content_revision"],
    )
    if identity != (VERSION, SOURCE, CLASSIFIER_VERSION, 1) or not opening["position_key"]:
        raise ValueError("current pinned opening classification unavailable")
    bounded(db, game_id, opening["dataset_id"])
    if _stale(db, game_id, opening):
        raise ValueError("opening classification is stale")
    return dict(opening)
