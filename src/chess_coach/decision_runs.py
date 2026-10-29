"""Find a position's cheap analysis without choosing partial deep runs."""


def cheap_run(db, game_id, position_id, run_id):
    query = """SELECT r.* FROM analysis_runs r WHERE r.game_id=?
        AND NOT EXISTS (SELECT 1 FROM deep_analysis_attempts a WHERE a.analysis_run_id=r.id)"""
    if run_id is not None:
        row = db.connection.execute(query + " AND r.id=?", (game_id, run_id)).fetchone()
        if row is None:
            raise ValueError("unknown cheap analysis run for decision")
        return row
    row = db.connection.execute(
        query
        + """ AND (EXISTS (SELECT 1 FROM decision_analysis_lines d
            WHERE d.run_id=r.id AND d.position_id=?) OR EXISTS (SELECT 1 FROM engine_outputs e
            WHERE e.run_id=r.id AND e.position_id=?)) ORDER BY r.id DESC LIMIT 1""",
        (game_id, position_id, position_id),
    ).fetchone()
    if row is not None:
        return row
    return db.connection.execute(
        query
        + """ AND NOT EXISTS (SELECT 1 FROM decision_analysis_lines d WHERE d.run_id=r.id)
        AND NOT EXISTS (SELECT 1 FROM engine_outputs e WHERE e.run_id=r.id)
        ORDER BY r.id DESC LIMIT 1""",
        (game_id,),
    ).fetchone()
