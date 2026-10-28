"""Print a synthetic, reviewable report of supported tactical decisions."""

import json

import chess
import chess.pgn

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.tactical_opportunities import record_game_opportunities

WHITE = "8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1"
BLACK = "2K5/8/2k5/4q3/8/8/8/8 b - - 0 1"
PINNED = "k3r3/8/8/8/8/3qR3/8/4K3 w - - 0 1"


def report(label: str, fen: str, move: str, learner: str) -> dict:
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "SyntheticWhite"
    game.headers["Black"] = "SyntheticBlack"
    game.add_variation(board.parse_uci(move))
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, str(game))
    candidates = record_game_opportunities(db, 1, learner=learner)
    db.close()
    return {"case": label, "candidates": candidates}


def main() -> None:
    cases = [
        ("white mate", WHITE, "e4c2", "SyntheticWhite"),
        ("white alternate mate", WHITE, "e4h1", "SyntheticWhite"),
        ("white stalemate", WHITE, "e4d3", "SyntheticWhite"),
        ("white ambiguous", WHITE, "e4e8", "SyntheticWhite"),
        ("black mate", BLACK, "e5c7", "SyntheticBlack"),
        ("black alternate mate", BLACK, "e5h8", "SyntheticBlack"),
        ("black stalemate", BLACK, "e5d6", "SyntheticBlack"),
        ("black ambiguous", BLACK, "e5e1", "SyntheticBlack"),
        ("pinned pseudo-capture", PINNED, "e3e4", "SyntheticWhite"),
        ("no mate", chess.STARTING_FEN, "e2e4", "SyntheticWhite"),
    ]
    print(json.dumps([report(*case) for case in cases], indent=2))


if __name__ == "__main__":
    main()
