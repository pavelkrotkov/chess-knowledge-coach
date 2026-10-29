"""Import comparison lines by stable game and ply without changing the source."""

from .analysis_comparison import save_comparison


def merge_comparisons(target, source, old_run, new_run, game_id, source_game_id):
    exists = source.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_analysis_lines'"
    ).fetchone()
    if not exists:
        return
    rows = source.connection.execute(
        """SELECT d.*, p.ply, p.game_id AS position_game FROM decision_analysis_lines d
        JOIN positions p ON p.id=d.position_id WHERE d.run_id=? ORDER BY d.id""",
        (old_run,),
    ).fetchall()
    if rows:
        _require_same_history(target, source, game_id, source_game_id)
    for row in rows:
        if row["position_game"] != source_game_id:
            raise ValueError("comparison position is not from its analysis game")
        position = target.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=?", (game_id, row["ply"])
        ).fetchone()
        if position is None:
            raise ValueError(f"target database is missing ply {row['ply']} for game {game_id}")
        data = dict(row)
        data["position_id"] = position["id"]
        save_comparison(target.connection, new_run, data)


def _require_same_history(target, source, game_id, source_game_id):
    old_game = source.connection.execute(
        "SELECT pgn FROM games WHERE id=?", (source_game_id,)
    ).fetchone()
    new_game = target.connection.execute("SELECT pgn FROM games WHERE id=?", (game_id,)).fetchone()
    if old_game is None or new_game is None or old_game[0] != new_game[0]:
        raise ValueError("comparison game history does not match target")
