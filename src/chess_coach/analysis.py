from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

import chess.engine

from .db import Database


def _cpu_flags() -> set[str]:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8")
    except OSError:
        return set()
    flags: set[str] = set()
    for line in text.splitlines():
        if line.lower().startswith(("flags", "features")) and ":" in line:
            flags.update(line.split(":", 1)[1].split())
    return flags


def detect_compatibility() -> dict[str, object]:
    machine = platform.machine().lower()
    flags = _cpu_flags()
    return {
        "machine": machine,
        "generic_x64": machine in {"x86_64", "amd64"},
        "popcnt": "popcnt" in flags if flags else None,
        "cpu_flags_available": bool(flags),
        "cpu_flags": sorted(flags),
    }


def _validate_config(
    nodes: int, depth: int | None, multipv: int, threads: int, hash_mb: int
) -> None:
    if nodes < 1 or (depth is not None and depth < 1) or multipv < 1 or threads < 1 or hash_mb < 1:
        raise ValueError("nodes, depth, MultiPV, threads, and hash must be positive")


def analyze_game(
    db: Database,
    game_id: int,
    engine_path: str = "/usr/games/stockfish",
    *,
    nodes: int = 20_000,
    depth: int | None = None,
    multipv: int = 1,
    threads: int = 1,
    hash_mb: int = 64,
) -> int:
    """Run a reproducible fixed-budget scan and persist all engine provenance."""
    _validate_config(nodes, depth, multipv, threads, hash_mb)
    binary = Path(engine_path).expanduser()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"engine binary is unavailable or not executable: {binary}")
    binary = binary.resolve()
    game = db.connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(binary))
    except (OSError, TimeoutError, chess.engine.EngineError) as exc:
        raise RuntimeError(f"could not start engine binary {binary}: {exc}") from exc
    try:
        info = engine.id
        engine.configure({"Threads": threads, "Hash": hash_mb})
        nnue_options = {
            name: str(option.default)
            for name, option in engine.options.items()
            if "nnue" in name.lower() or "evalfile" in name.lower()
        }
        compatibility = detect_compatibility()
        config = {
            "nodes": nodes,
            "depth": depth,
            "multipv": multipv,
            "threads": threads,
            "hash_mb": hash_mb,
            "engine_path": str(binary),
            "compatibility": compatibility,
            "nnue_options": nnue_options,
        }
        binary_version = info.get("name", info.get("unicode", "unknown"))
        run = db.connection.execute(
            """INSERT INTO analysis_runs
            (game_id, engine, engine_version, config_json, binary_path, binary_version, nnue, compatibility_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                info.get("name", "unknown"),
                info.get("unicode", info.get("author", "unknown")),
                json.dumps(config, sort_keys=True),
                str(binary),
                binary_version,
                json.dumps(nnue_options, sort_keys=True),
                json.dumps(compatibility, sort_keys=True),
            ),
        )
        if run.lastrowid is None:
            raise RuntimeError("SQLite did not return an analysis run id")
        run_id = run.lastrowid
        for position in db.connection.execute(
            "SELECT * FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
        ):
            board = chess.Board(position["fen"])
            limit: dict[str, Any] = {"nodes": nodes}
            if depth is not None:
                limit["depth"] = depth
            result = engine.analyse(board, chess.engine.Limit(**limit), multipv=multipv)
            lines = result if isinstance(result, list) else [result]
            for line_number, best in enumerate(lines, start=1):
                score = best["score"].pov(board.turn).score(mate_score=100000)
                db.connection.execute(
                    """INSERT INTO engine_outputs
                    (run_id, position_id, score_cp, best_move, played_move, multipv, pv, nodes, depth)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        position["id"],
                        score,
                        best["pv"][0].uci(),
                        position["uci"],
                        line_number,
                        " ".join(move.uci() for move in best["pv"]),
                        best.get("nodes"),
                        best.get("depth"),
                    ),
                )
        db.connection.commit()
        return int(run_id)
    finally:
        engine.quit()


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
                    (run_id, position_id, score_cp, wdl_json, best_move, played_move, multipv, pv, nodes, depth)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    ),
                )
                imported += 1
        target.connection.commit()
        return imported
    except Exception:
        target.connection.rollback()
        raise
