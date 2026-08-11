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
        "popcnt": "popcnt" in flags,
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
    binary = Path(engine_path)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"engine binary is unavailable or not executable: {binary}")
    game = db.connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(binary))
    except (OSError, chess.engine.EngineError) as exc:
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
        binary_version = info.get("author", info.get("unicode", "unknown"))
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
                limit = {"depth": depth}
            result = engine.analyse(board, chess.engine.Limit(**limit), multipv=multipv)
            best = result[0] if isinstance(result, list) else result
            score = best["score"].pov(board.turn).score(mate_score=100000)
            db.connection.execute(
                """INSERT INTO engine_outputs
                (run_id, position_id, score_cp, best_move, played_move, pv, nodes, depth)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    position["id"],
                    score,
                    best["pv"][0].uci(),
                    position["uci"],
                    " ".join(move.uci() for move in best["pv"]),
                    best.get("nodes"),
                    best.get("depth"),
                ),
            )
        db.connection.commit()
        return int(run_id)
    finally:
        engine.quit()
