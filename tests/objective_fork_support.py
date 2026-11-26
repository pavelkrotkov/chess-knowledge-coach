"""Create fully synthetic, analyzed owned-fork fixtures."""

import sys

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.fork_detector import process_decision
from chess_coach.fork_proof import fork_proof
from chess_coach.ingest import ingest_pgn
from chess_coach.material_opportunity_source import load_source
from chess_coach.objective_contract import OWNED_HISTORY
from chess_coach.objective_fork_contract import GOAL, OBJECTIVE, VERSION
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_sessions import start
from tests.test_fork_pipeline import Engine

SUBJECT = "fixture_learner"
FEN = "b3k3/4B2p/5K2/1N3b2/8/8/8/8 w - - 0 1"
ANCHOR_FEN = "b3k3/7p/5K2/1NB2b2/8/8/8/8 w - - 0 1"


class ForkEngine(Engine):
    def __init__(self, *, mirrored=False, source_fen=FEN):
        super().__init__()
        self.mirrored = mirrored
        self.source_fen = source_fen

    def analyse(self, board, limit, multipv, root_moves=None):
        def normal(move):
            return _mirror(move) if self.mirrored else move

        missed = root_moves and normal(root_moves[0].uci()) == "f6g5"
        moves = ["f6g5", "e8d7", "b5c7", "f5e6"] if missed else ["b5c7", "e8d7", "c7a8", "f5e6"]
        observed = board.mirror() if self.mirrored else board
        if observed.board_fen() != chess.Board(self.source_fen).board_fen():
            return [
                {
                    "score": chess.engine.PovScore(
                        chess.engine.Cp(0 if missed else 600), board.turn
                    ),
                    "pv": [root_moves[0] if root_moves else next(iter(board.legal_moves))],
                    "nodes": 100,
                    "depth": 5,
                }
            ]
        moves = [normal(move) for move in moves]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0 if missed else 600), board.turn),
                "pv": [chess.Move.from_uci(move) for move in moves],
                "nodes": 100,
                "depth": 5,
            }
        ]


def _mirror(move):
    value = chess.Move.from_uci(move)
    return chess.Move(
        chess.square_mirror(value.from_square),
        chess.square_mirror(value.to_square),
        promotion=value.promotion,
    ).uci()


def owned_fork(
    path, monkeypatch, played, *, with_history=False, mirrored=False, anchor_layout=False
):
    source_fen = ANCHOR_FEN if anchor_layout else FEN
    board = chess.Board("b7/3kB2p/5K2/1N3b2/8/8/8/8 b - - 0 1" if with_history else source_fen)
    if mirrored:
        board = board.mirror()
    move = _mirror if mirrored else (lambda value: value)
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if mirrored else SUBJECT,
            "Black": SUBJECT if mirrored else "fixture_opponent",
            "Result": "*",
        }
    )
    node = game
    if with_history:
        node = node.add_variation(board.parse_uci(move("d7e8")))
        board.push_uci(move("d7e8"))
    node = node.add_variation(board.parse_uci(move(played)))
    board.push_uci(move(played))
    node.add_variation(board.parse_uci(move("e8d7")))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda _: ForkEngine(mirrored=mirrored, source_fen=source_fen),
    )
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    evidence = process_decision(db, 2 if with_history else 1, SUBJECT)["evidence_ids"][0]
    return db, evidence


def begin(db, evidence, attempt="fork", *, version=VERSION):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=version,
        key=str(evidence),
    )


# Frozen constructor from d30d82e3dc0e161afb559a7dff175da9b6da7e1c;
# original blob e92874e7ab5c7a8713f4521a8b8bfbc4fdc82014.
def previous_snapshot(db, board, evidence, fact, *, objective=OBJECTIVE, check=None):
    original = fact["payload"]["proof"]
    move = board.parse_uci(original["move"])
    options = {"check": check} if check is not None else {}
    if fork_proof(board, move, **options) != original:
        raise ValueError("fork certificate changed")
    anchor = _previous_anchor(board, original["targets"])
    reviews = evidence["reviews"]
    source = load_source(db, fact["detector_run_id"])
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": GOAL,
        "lines": [move.uci()],
        "provenance": {
            "source_fingerprint": source["source_marker"],
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": reviews[-1]["id"] if reviews else None,
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": evidence["mapper_version"],
            "fact_id": fact["id"],
            "detector_run_id": fact["detector_run_id"],
            "fork_certificate": original,
            "objective_version": objective,
            "history_mode": OWNED_HISTORY,
            "fork_attacker": chess.square_name(move.from_square),
            "fork_anchor": anchor,
            "gain_threshold": 3,
            "source_outcome": evidence["outcome"],
        },
    }


def _previous_anchor(board, targets):
    kings = [
        square
        for square in targets
        if board.piece_at(chess.parse_square(square)).piece_type == chess.KING
    ]
    return kings[0] if kings else targets[0]
