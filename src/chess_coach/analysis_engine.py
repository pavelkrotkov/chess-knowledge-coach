"""Engine configuration, run provenance, and per-decision output persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import chess.engine

from .analysis_output import save_line


def create_run(
    connection: sqlite3.Connection,
    game_id: int,
    binary: Path,
    engine: chess.engine.SimpleEngine,
    config: dict[str, object],
) -> int:
    info = engine.id
    nnue = {
        name: str(option.default)
        for name, option in engine.options.items()
        if "nnue" in name.lower() or "evalfile" in name.lower()
    }
    config["nnue_options"] = nnue
    config["engine_id"] = dict(info)
    run = connection.execute(
        """INSERT INTO analysis_runs
        (game_id, engine, engine_version, config_json, binary_path, binary_version, nnue, compatibility_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            game_id,
            info.get("name", "unknown"),
            info.get("name", info.get("unicode", "unknown")),
            json.dumps(config, sort_keys=True),
            str(binary),
            info.get("name", info.get("unicode", "unknown")),
            json.dumps(nnue, sort_keys=True),
            json.dumps(config["compatibility"], sort_keys=True),
        ),
    )
    if run.lastrowid is None:
        raise RuntimeError("SQLite did not return an analysis run id")
    return run.lastrowid


def scan(
    connection: sqlite3.Connection,
    engine: chess.engine.SimpleEngine,
    run_id: int,
    game: sqlite3.Row,
    *,
    nodes: int,
    depth: int | None,
    multipv: int,
) -> None:
    from .analysis_positions import decisions

    for position, board in decisions(connection, game):
        result = engine.analyse(
            board, chess.engine.Limit(nodes=nodes, depth=depth), multipv=multipv
        )
        lines = result if isinstance(result, list) else [result]
        for number, line in enumerate(lines or [{}], start=1):
            save_line(connection, run_id, position, board, number, dict(line))
