"""Classify games against a versioned opening dataset."""

from __future__ import annotations

from .classification_transaction import classification_transaction
from .db import Database
from .opening_history import persist_opening

CLASSIFIER_VERSION = "1.1.0"


def classify_game(
    db: Database,
    game_id: int,
    *,
    version: str,
    source_url: str,
    classifier_version: str = CLASSIFIER_VERSION,
    pipeline_generation: int | None = None,
) -> dict[str, object]:
    if not isinstance(classifier_version, str) or not classifier_version.strip():
        raise ValueError("classifier version must be nonempty")
    with classification_transaction(db):
        dataset_id = _dataset_for_game(db, game_id, version, source_url)
        best = _best_match(db, game_id, dataset_id)
        return persist_opening(
            db, game_id, dataset_id, classifier_version, best, pipeline_generation
        )


def _dataset_for_game(db: Database, game_id: int, version: str, source_url: str) -> int:
    game = db.connection.execute("SELECT variant FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    if game["variant"] != "Standard":
        raise ValueError(f"opening classification does not support variant {game['variant']!r}")
    dataset = db.connection.execute(
        "SELECT id FROM opening_datasets WHERE version = ? AND source_url = ?",
        (version, source_url),
    ).fetchone()
    if dataset is None:
        raise ValueError(f"opening dataset {version!r} is not imported")
    return dataset[0]


def _best_match(db: Database, game_id: int, dataset_id: int):
    best = None
    for position in db.connection.execute(
        "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
    ):
        key = " ".join(position["fen"].split()[:4])
        node = db.connection.execute(
            """SELECT id, eco, name, ply FROM opening_nodes
            WHERE dataset_id = ? AND position_key = ? ORDER BY ply DESC, id LIMIT 1""",
            (dataset_id, key),
        ).fetchone()
        if node is not None:
            best = node
    return best
