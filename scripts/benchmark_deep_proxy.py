"""Measure bounded synthetic decisions against a longer Stockfish search.

No game files, database, account identity or application configuration are read.
The same engine and synthetic positions are used for every budget. One best-search
node count is shared by all MultiPV alternatives; the forced root is separate.
"""

import json
import os

import chess
import chess.engine
from benchmark_deep_search import search

POSITIONS = {
    "tactical_hanging": "4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1",
    "tactical_fork": "4k3/8/2N5/8/1r1q4/8/8/4K3 w - - 0 1",
    "tactical_mate": "8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1",
    "middlegame": "r2q1rk1/ppp2ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP2PPP/R2Q1RK1 w - - 4 9",
    "endgame": "8/5k2/8/3P4/8/4K3/8/8 w - - 0 1",
    "black_middlegame": "r2q1rk1/ppp2ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP2PPP/R2Q1RK1 b - - 4 9",
}
BUDGETS = ((5000, 1.0), (20000, 1.0), (50000, 2.0), (200000, 8.0))


def main():
    result = {"load_average": list(os.getloadavg()), "threads": 1, "positions": {}}
    with chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish", timeout=5) as engine:
        engine.configure({"Threads": 1, "Hash": 64})
        result["engine"] = engine.id.get("name", "unknown")
        for label, fen in POSITIONS.items():
            board = chess.Board(fen)
            if not board.is_valid() or board.is_game_over():
                raise ValueError(f"invalid synthetic position: {label}")
            runs = []
            for nodes, seconds in BUDGETS:
                sample = search(engine, board, nodes, seconds)
                sample.update({"node_limit_per_search": nodes, "seconds_per_search": seconds})
                runs.append(sample)
            reference = runs[-1]["best_move"]
            for sample in runs:
                sample["best_move_disagrees_with_reference"] = sample["best_move"] != reference
            result["positions"][label] = runs
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
