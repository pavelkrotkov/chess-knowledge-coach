"""Atomic analysis import for offline engine handoffs."""

from __future__ import annotations

from .db import Database


def merge_analysis_outputs(target: Database, source: Database) -> int:
    """Atomically import analysis runs by stable game source identity and game ply."""
    imported = 0
    try:
        target.connection.execute("BEGIN IMMEDIATE")
        runs = source.connection.execute(
            """SELECT runs.*, games.source AS game_source, games.source_id
            FROM analysis_runs AS runs JOIN games ON games.id = runs.game_id ORDER BY runs.id"""
        ).fetchall()
        for run in runs:
            game = target.connection.execute(
                "SELECT id FROM games WHERE source = ? AND source_id = ?",
                (run["game_source"], run["source_id"]),
            ).fetchone()
            if game is None:
                raise ValueError(
                    f"target database is missing source game {run['game_source']}:{run['source_id']}"
                )
            cursor = target.connection.execute(
                """INSERT INTO analysis_runs
                (game_id, engine, engine_version, config_json, binary_path, binary_version, nnue, compatibility_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    game["id"],
                    run["engine"],
                    run["engine_version"],
                    run["config_json"],
                    run["binary_path"],
                    run["binary_version"],
                    run["nnue"],
                    run["compatibility_json"],
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an imported analysis run id")
            outputs = source.connection.execute(
                """SELECT outputs.*, positions.ply FROM engine_outputs AS outputs
                JOIN positions ON positions.id = outputs.position_id
                WHERE outputs.run_id = ? ORDER BY outputs.id""",
                (run["id"],),
            ).fetchall()
            for output in outputs:
                output_fields = dict(output)
                position = target.connection.execute(
                    "SELECT id FROM positions WHERE game_id = ? AND ply = ?",
                    (game["id"], output["ply"]),
                ).fetchone()
                if position is None:
                    raise ValueError(
                        f"target database is missing ply {output['ply']} for game {game['id']}"
                    )
                target.connection.execute(
                    """INSERT INTO engine_outputs
                    (run_id, position_id, score_cp, wdl_json, best_move, played_move, multipv, pv, nodes, depth, decision_fen, score_pov)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cursor.lastrowid,
                        position["id"],
                        output["score_cp"],
                        output["wdl_json"],
                        output["best_move"],
                        output["played_move"],
                        output["multipv"],
                        output["pv"],
                        output["nodes"],
                        output["depth"],
                        output_fields.get("decision_fen"),
                        output_fields.get("score_pov"),
                    ),
                )
                imported += 1
        target.connection.commit()
        return imported
    except Exception:
        target.connection.rollback()
        raise
