"""Batch source-bound purpose decisions within one report snapshot."""

from .deep_selection_source import MAX_DECISIONS
from .purpose_source_batch_item import snapshot_item
from .purpose_source_binding import history_fingerprint, owned_game
from .style_history import selected_boards


def snapshots(db, game_id, learner, position_ids, *, boards=None):
    game, color = owned_game(db, game_id, learner)
    rows = db.connection.execute(
        "SELECT id,ply,fen,uci FROM positions WHERE game_id=? ORDER BY ply", (game_id,)
    ).fetchall()
    if len(rows) > MAX_DECISIONS:
        return {}
    fingerprint = history_fingerprint(game, color, rows)
    if boards is None:
        boards = selected_boards(db, game_id, position_ids)
    result = {}
    for position_id, board in boards.items():
        item = snapshot_item(db, game_id, color, learner, fingerprint, position_id, board)
        if item is not None:
            result[position_id] = item
    return result
