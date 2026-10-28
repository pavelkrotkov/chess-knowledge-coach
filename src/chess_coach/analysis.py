from __future__ import annotations

import platform
import sqlite3
from collections.abc import Callable
from pathlib import Path

import chess.engine

from .analysis_configuration import engine_config
from .analysis_merge import merge_analysis_outputs as merge_analysis_outputs
from .analysis_transaction import run as run_transaction
from .analysis_validation import prepare, validate_time
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
    time_limit: float | None = None,
    on_complete: Callable[[sqlite3.Connection, int], None] | None = None,
) -> int:
    """Scan pre-move decisions and commit only a complete engine run."""
    validate_time(time_limit)
    binary, game = prepare(
        db.connection, game_id, engine_path, nodes, depth, multipv, threads, hash_mb
    )
    config = engine_config(
        binary, nodes, time_limit, depth, multipv, threads, hash_mb, detect_compatibility()
    )
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(binary))
    except (OSError, TimeoutError, chess.engine.EngineError) as exc:
        raise RuntimeError(f"could not start engine binary {binary}: {exc}") from exc
    return run_transaction(
        db, game_id, binary, game, engine, config, nodes, depth, multipv, time_limit, on_complete
    )
