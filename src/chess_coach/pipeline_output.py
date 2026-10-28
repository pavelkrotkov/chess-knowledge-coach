"""Check that checkpointed producer output is still current and complete."""

import sqlite3

from .fact_fingerprint import canonical, digest


def output_is_current(connection: sqlite3.Connection, row) -> bool:
    if row["status"] == "skipped":
        return True
    if row["stage"] == "analysis":
        return _analysis_exists(connection, row)
    if row["stage"] in {"structures", "opening"}:
        table = {"structures": "structure_runs", "opening": "opening_runs"}[row["stage"]]
        return (
            connection.execute(
                f'SELECT 1 FROM {table} WHERE id=? AND game_id=? AND status="active"',
                (row["output_id"], row["game_id"]),
            ).fetchone()
            is not None
        )
    if row["stage"] == "tactical":
        return row["output_hash"] == tactical_output_hash(connection, row["game_id"])
    return True


def _analysis_exists(connection: sqlite3.Connection, row) -> bool:
    run = connection.execute(
        "SELECT id FROM analysis_runs WHERE id=? AND game_id=?", (row["output_id"], row["game_id"])
    ).fetchone()
    if run is None:
        return False
    missing = connection.execute(
        """SELECT COUNT(*) FROM positions p WHERE p.game_id=? AND NOT EXISTS (
        SELECT 1 FROM engine_outputs e WHERE e.run_id=? AND e.position_id=p.id AND e.multipv=1
        AND e.decision_fen IS NOT NULL AND e.score_pov IS NOT NULL AND e.played_move=p.uci)""",
        (row["game_id"], row["output_id"]),
    ).fetchone()[0]
    return missing == 0


def tactical_output_hash(connection: sqlite3.Connection, game_id: int) -> str:
    facts = [
        row[0]
        for row in connection.execute(
            """SELECT d.id FROM detector_runs d JOIN positions p ON p.id=d.position_id
        WHERE p.game_id=? AND d.producer="mate-in-one" AND d.status="active" ORDER BY d.id""",
            (game_id,),
        )
    ]
    mappings = [
        row[0]
        for row in connection.execute(
            """SELECT m.id FROM mapping_runs m JOIN positions p ON p.id=m.position_id
        WHERE p.game_id=? AND m.producer="mate-in-one-mapper" AND m.status="active" ORDER BY m.id""",
            (game_id,),
        )
    ]
    return digest(canonical({"facts": facts, "mappings": mappings}))
