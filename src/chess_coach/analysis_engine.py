"""Engine configuration, run provenance, and per-decision output persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import chess.engine

from .analysis_comparison import comparison_line
from .analysis_output import line_fields


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
    game: sqlite3.Row,
    spool,
    *,
    nodes: int,
    depth: int | None,
    multipv: int,
    time_limit: float | None = None,
) -> None:
    from .analysis_positions import decisions

    limit = chess.engine.Limit(nodes=nodes, depth=depth, time=time_limit)
    for position, board in decisions(connection, game):
        _scan_decision(engine, position, board, limit, multipv, spool)


def _scan_decision(engine, position, board, limit, multipv, spool):
    result = engine.analyse(board, limit, multipv=multipv)
    lines = result if isinstance(result, list) else [result]
    for number, line in enumerate(lines or [{}], start=1):
        _spool(spool, line_fields(position, board, number, dict(line)))
    best = dict(lines[0]) if lines else {}
    played_move = board.parse_uci(position["uci"])
    forced = engine.analyse(board, limit, multipv=1, root_moves=[played_move])
    forced_lines = forced if isinstance(forced, list) else [forced]
    played = dict(forced_lines[0]) if forced_lines else {}
    for role, line in (("best", best), ("played", played)):
        _spool(spool, comparison_line(position, board, role, line))


def _spool(spool, value):
    json.dump(value, spool)
    spool.write("\n")
