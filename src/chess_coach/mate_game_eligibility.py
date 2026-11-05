"""Check bounded and finished game records before replay."""

import io

import chess.pgn

from .objective_source_budget import MAX_GAME_BYTES


def require_game(db, game):
    if len(game["pgn"].encode("utf-8")) > MAX_GAME_BYTES:
        raise ValueError("game exceeds size limit")
    if db.connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET 1000", (game["id"],)
    ).fetchone():
        raise ValueError("game exceeds replay limit")
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    if not headers or headers.get("Result") != game["result"]:
        raise ValueError("game result is inconsistent")
    if game["result"] not in {"1-0", "0-1", "1/2-1/2"}:
        raise ValueError("game is unfinished")


def require_consistent_result(game, pairs):
    """Reject a result that contradicts a forced terminal board."""
    context, board = pairs[-1]
    board = board.copy()
    board.push_uci(context["played_move"])
    outcome = board.outcome(claim_draw=False)
    if outcome is not None and outcome.result() != game["result"]:
        raise ValueError("game result contradicts terminal board")
