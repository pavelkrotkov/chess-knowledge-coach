"""Find a current opening name at the pre-move position."""

from .opening_storage import position_key
from .repertoire_game import _opening, _stale


def current_opening(db, game_id):
    opening = _opening(db, game_id)
    return opening if opening is not None and not _stale(db, game_id, opening) else None


def opening_context(db, opening, board):
    if opening is None:
        return {"name": "unknown", "dataset": None}
    node = db.connection.execute(
        """SELECT eco,name FROM opening_nodes WHERE dataset_id=? AND position_key=?
        ORDER BY ply DESC,id LIMIT 1""",
        (opening["dataset_id"], position_key(board)),
    ).fetchone()
    return {
        "name": f"{node['eco'] or '?'} {node['name']}" if node else "unknown",
        "dataset": {
            "version": opening["version"],
            "source_url": opening["source_url"],
            "classification_run": opening["run_id"],
        },
    }
