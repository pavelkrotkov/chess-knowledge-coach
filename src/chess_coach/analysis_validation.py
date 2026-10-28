"""Validate engine configuration and analysis inputs before starting a run."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def prepare(
    connection: sqlite3.Connection,
    game_id: int,
    engine_path: str,
    nodes: int,
    depth: int | None,
    multipv: int,
    threads: int,
    hash_mb: int,
) -> tuple[Path, sqlite3.Row]:
    validate_config(nodes, depth, multipv, threads, hash_mb)
    if connection.in_transaction:
        raise RuntimeError("cannot analyze during an existing transaction")
    binary = Path(engine_path).expanduser()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"engine binary is unavailable or not executable: {binary}")
    game = connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    return binary.resolve(), game


def validate_config(
    nodes: int, depth: int | None, multipv: int, threads: int, hash_mb: int
) -> None:
    if nodes < 1 or (depth is not None and depth < 1) or multipv < 1 or threads < 1 or hash_mb < 1:
        raise ValueError("nodes, depth, MultiPV, threads, and hash must be positive")
