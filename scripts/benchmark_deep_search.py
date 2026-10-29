"""Measure native work and wall time for one synthetic decision."""

import time

import chess.engine


def search(engine, board, nodes, seconds):
    engine.configure({"Clear Hash": None})
    legal = list(board.legal_moves)
    limit = chess.engine.Limit(nodes=nodes, time=seconds)
    started = time.monotonic()
    best = engine.analyse(board, limit, multipv=min(3, len(legal)))
    played = engine.analyse(board, limit, root_moves=[legal[-1]])
    elapsed = time.monotonic() - started
    return {
        "best_move": best[0]["pv"][0].uci(),
        "best_depth": best[0].get("depth"),
        "best_score": str(best[0]["score"].pov(board.turn)),
        "played_score": str(played["score"].pov(board.turn)),
        "best_shared_nodes": max(line.get("nodes", 0) for line in best),
        "played_nodes": played.get("nodes"),
        "played_depth": played.get("depth"),
        "elapsed_seconds": round(elapsed, 4),
    }
