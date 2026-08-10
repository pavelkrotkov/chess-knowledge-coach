from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chess.engine

from .db import Database


def analyze_game(db: Database, game_id: int, engine_path: str = "/usr/games/stockfish",
                 *, nodes: int = 20_000, depth: int | None = None,
                 multipv: int = 1, threads: int = 1, hash_mb: int = 64) -> int:
    """Run a reproducible fixed-budget scan and persist all engine provenance."""
    game = db.connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    engine = chess.engine.SimpleEngine.popen_uci(str(Path(engine_path)))
    try:
        info = engine.id
        engine.configure({"Threads": threads, "Hash": hash_mb})
        config = {"nodes": nodes, "depth": depth, "multipv": multipv,
                  "threads": threads, "hash_mb": hash_mb}
        run = db.connection.execute(
            "INSERT INTO analysis_runs (game_id, engine, engine_version, config_json) VALUES (?, ?, ?, ?)",
            (game_id, info.get("name", "unknown"), info.get("unicode", info.get("author", "unknown")),
             json.dumps(config, sort_keys=True)),
        )
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
                (run_id, position["id"], score, best["pv"][0].uci(), position["uci"],
                 " ".join(move.uci() for move in best["pv"]), best.get("nodes"), best.get("depth")),
            )
        db.connection.commit()
        return int(run_id)
    finally:
        engine.quit()
