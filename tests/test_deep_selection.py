"""Manual selection is bounded, reproducible and never produces mastery evidence."""

import json
import sys

import chess
import chess.engine
import pytest

from chess_coach.db import Database
from chess_coach.deep_selection import select_deep
from chess_coach.deep_selection_views import list_selections, show_selection
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis

LEARNER = "fixture_learner"
OPPONENT = "fixture_opponent"
PGN = """[Event "Synthetic"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:00"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 d6 5. c3 Be7 6. O-O O-O *
"""


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        ply = len(board.move_stack)
        played = root_moves is not None
        move = root_moves[0] if played else next(iter(board.legal_moves))
        score = chess.engine.Cp(0)
        if ply == 0 and not played:
            score = chess.engine.Cp(300)
        if ply == 4:
            score = chess.engine.Mate(3)
        wdl = chess.engine.Wdl(500, 200, 300)
        if ply == 6 and not played:
            wdl = chess.engine.Wdl(900, 50, 50)
        result = {
            "score": chess.engine.PovScore(score, board.turn),
            "pv": [move],
            "wdl": chess.engine.PovWdl(wdl, board.turn),
            "nodes": 100,
            "depth": 5,
        }
        if ply == 2:
            result["lowerbound"] = True
        return [result]

    def quit(self):
        pass


def setup_game(path, monkeypatch, *, count=1):
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    for number in range(count):
        ingest_pgn(db, PGN.replace('Event "Synthetic"', f'Event "Synthetic {number}"'))
        game_id = number + 1
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        result = run_analysis(
            db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
        )
        assert result["status"] == "complete"
    return db


def named_motifs(board):
    return [{"motif": "fork"}] if len(board.move_stack) == 0 else []


def test_bounded_replay_context_reasons_and_no_mastery(tmp_path, monkeypatch):
    from chess_coach import deep_selection_reasons

    db = setup_game(tmp_path / "selection.sqlite", monkeypatch)
    monkeypatch.setattr(deep_selection_reasons, "detect_motifs", named_motifs)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _: pytest.fail("selector reran engine")
    )
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    first = select_deep(db, [1], learner=LEARNER, per_game=4, total=4)
    again = select_deep(db, [1], learner=LEARNER, per_game=4, total=4)
    assert first == again
    detail = show_selection(db, 1, LEARNER)
    assert detail["state"] == "current" and detail["coverage"]["eligible"] == 6
    assert detail["coverage"]["control_target"] == 1 and detail["coverage"]["selected"] == 4
    assert detail["coverage"]["nominated"]["score"] == 2
    assert detail["coverage"]["nominated"]["uncertain"] == 2
    assert detail["coverage"]["nominated"]["opportunity"] == 1
    assert detail["coverage"]["overlapping_nominations"] == 1
    assert detail["coverage"]["reason_counts"]["cp_score_gap"] == 1
    assert detail["coverage"]["reason_counts"]["wdl_score_gap"] == 1
    assert detail["coverage"]["reason_counts"]["bounded_score"] == 1
    assert detail["coverage"]["reason_counts"]["mate_score"] == 1
    assert detail["coverage"]["reason_counts"]["possible_fork"] == 1
    assert all(
        item["status"] == "pending_deep" and item["ply"] % 2 == 1 for item in detail["items"]
    )
    assert any("control_sample" in item["reasons"] for item in detail["items"])
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    public = json.dumps([first, detail, list_selections(db, LEARNER)])
    assert LEARNER not in public and OPPONENT not in public and "fingerprint" not in public
    assert '"learner_key"' not in public and PGN not in public


def test_config_generations_stale_detection_and_reactivation(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "history.sqlite", monkeypatch)
    first = select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    first_id = first["games"][0]["selection_id"]
    second = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    assert second["games"][0]["selection_id"] != first_id
    assert show_selection(db, 1, LEARNER, selection_id=first_id)["state"] == "historical"
    assert select_deep(db, [1], learner=LEARNER, per_game=3, total=3) == first
    assert show_selection(db, 1, LEARNER)["selection_id"] == first_id
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 2
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    assert show_selection(db, 1, LEARNER)["state"] == "stale"
    changed = select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    assert changed["games"][0]["selection_id"] != first_id
