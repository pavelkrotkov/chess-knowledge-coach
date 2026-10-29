"""Create fully synthetic, analyzed owned-fork fixtures."""

import sys

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.fork_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.objective_fork_contract import VERSION
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_sessions import start
from tests.test_fork_pipeline import Engine

SUBJECT = "fixture_learner"
FEN = "b3k3/4B2p/5K2/1N3b2/8/8/8/8 w - - 0 1"


class ForkEngine(Engine):
    def analyse(self, board, limit, multipv, root_moves=None):
        missed = root_moves and root_moves[0].uci() == "f6g5"
        moves = ["f6g5", "e8d7", "b5c7", "f5e6"] if missed else ["b5c7", "e8d7", "c7a8", "f5e6"]
        if board.board_fen() != chess.Board(FEN).board_fen():
            moves = [root_moves[0].uci() if root_moves else next(iter(board.legal_moves)).uci()]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0 if missed else 600), board.turn),
                "pv": [chess.Move.from_uci(move) for move in moves],
                "nodes": 100,
                "depth": 5,
            }
        ]


def owned_fork(path, monkeypatch, played, *, with_history=False):
    board = chess.Board("b7/3kB2p/5K2/1N3b2/8/8/8/8 b - - 0 1" if with_history else FEN)
    game = chess.pgn.Game.from_board(board)
    game.headers.update({"White": SUBJECT, "Black": "fixture_opponent", "Result": "*"})
    node = game
    if with_history:
        node = node.add_variation(board.parse_uci("d7e8"))
        board.push_uci("d7e8")
    node = node.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci("e8d7"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: ForkEngine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    evidence = process_decision(db, 2 if with_history else 1, SUBJECT)["evidence_ids"][0]
    return db, evidence


def begin(db, evidence, attempt="fork"):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )
