"""Stable identities for game positions and opening dataset contents."""

from .db import Database
from .fact_fingerprint import canonical, digest


def position_input(db: Database, game_id: int) -> list[list]:
    return [
        list(row)
        for row in db.connection.execute(
            "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
        )
    ]


def opening_input(db: Database, game_id: int, dataset_id: int) -> str:
    nodes = [
        list(row)
        for row in db.connection.execute(
            """SELECT position_key, eco, name, ply FROM opening_nodes
        WHERE dataset_id = ? ORDER BY position_key, eco, name, ply""",
            (dataset_id,),
        )
    ]
    edges = [
        list(row)
        for row in db.connection.execute(
            """SELECT parent_key, child_key, uci FROM opening_edges
        WHERE dataset_id = ? ORDER BY parent_key, child_key, uci""",
            (dataset_id,),
        )
    ]
    return digest(
        canonical({"positions": position_input(db, game_id), "nodes": nodes, "edges": edges})
    )
