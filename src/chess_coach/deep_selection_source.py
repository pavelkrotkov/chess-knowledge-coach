"""Read a current cheap-analysis snapshot without exposing game identities."""

from .db import Database
from .deep_selection_checkpoint import validate_checkpoint
from .deep_selection_fingerprint import source_payload
from .deep_selection_source_rows import analysis_lines, current_analysis
from .fact_fingerprint import canonical, digest
from .learner_identity import learner_color, normalize_identity

MAX_DECISIONS = 1000


def learner_key(learner):
    name = normalize_identity(learner)
    if name is None:
        raise ValueError("learner identity is unavailable")
    return digest("deep-selection-learner-v1:" + name)


def source_snapshot(db: Database, game_id: int, learner: str) -> dict:
    game = db.connection.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        raise ValueError("game is unavailable")
    color = learner_color(game, learner)
    if color is None:
        raise ValueError("learner is not attributable to this game")
    rows = db.connection.execute(
        "SELECT id,ply,fen,uci FROM positions WHERE game_id=? ORDER BY ply", (game_id,)
    ).fetchall()
    if len(rows) > MAX_DECISIONS:
        raise ValueError("game exceeds the selection decision limit")
    stage, run, config = current_analysis(db, game_id)
    validate_checkpoint(db, game_id, stage, config)
    lines = analysis_lines(db, run["id"], game_id)
    stable_game = digest(canonical({"pgn": game["pgn"], "color": color}))
    payload = source_payload(game, color, rows, lines, config)
    return {
        "game": game,
        "color": color,
        "positions": rows,
        "lines": lines,
        "cheap_run_id": run["id"],
        "input_fingerprint": digest(canonical(payload)),
        "game_key": stable_game,
    }
