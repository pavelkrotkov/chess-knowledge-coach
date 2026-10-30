"""Reconstruct requested boards once within the report read snapshot."""

import io

import chess.pgn


def boards(db, game_id, ids, history):
    if not ids:
        return {}
    last = _last_position(db, game_id)
    if last is None:
        return {}
    history.targets(set(ids) | {last["id"]})
    try:
        history.board(game_id, last["id"])
        return {position: history.board(game_id, position) for position in ids}
    except (ValueError, TypeError, IndexError):
        return {}


def _last_position(db, game_id):
    game = db.connection.execute("SELECT pgn FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        return None
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    if headers is None or "FEN" in headers or headers.get("SetUp") == "1":
        return None
    return db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? ORDER BY ply DESC LIMIT 1", (game_id,)
    ).fetchone()
