from __future__ import annotations

import platform
from contextlib import suppress
from pathlib import Path

import chess.engine

from .analysis_engine import create_run, scan
from .analysis_merge import merge_analysis_outputs as merge_analysis_outputs
from .analysis_validation import prepare
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
    """Scan pre-move decisions and commit only a complete engine run."""
    binary, game = prepare(
        db.connection, game_id, engine_path, nodes, depth, multipv, threads, hash_mb
    )
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(binary))
    except (OSError, TimeoutError, chess.engine.EngineError) as exc:
        raise RuntimeError(f"could not start engine binary {binary}: {exc}") from exc
    try:
        engine.configure({"Threads": threads, "Hash": hash_mb})
        config: dict[str, object] = {
            "nodes": nodes,
            "depth": depth,
            "multipv": multipv,
            "threads": threads,
            "hash_mb": hash_mb,
            "engine_path": str(binary),
            "compatibility": detect_compatibility(),
            "position_semantics": "pre_move_v1",
            "score_perspective": "side_to_move",
            "mate_score": 100000,
        }
        db.connection.execute("BEGIN IMMEDIATE")
        run_id = create_run(db.connection, game_id, binary, engine, config)
        scan(db.connection, engine, run_id, game, nodes=nodes, depth=depth, multipv=multipv)
        engine.quit()
        db.connection.commit()
        return run_id
    except BaseException:
        db.connection.rollback()
        with suppress(Exception):
            engine.quit()
        raise
