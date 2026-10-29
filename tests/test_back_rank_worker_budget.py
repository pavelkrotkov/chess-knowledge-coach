"""Back-rank attempts share the configured mate decision limit."""

import sys

import pytest

from chess_coach import back_rank_auto, back_rank_worker_item
from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.mate_auto import process_decision as process_mate
from chess_coach.mate_worker import process_mates
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from tests.test_mate_proof import owned_game

FEN = "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"


def two_decisions(path, monkeypatch):
    db = owned_game(path, monkeypatch, fen=FEN, move="Re2")
    pgn = f'''[Event "Second synthetic game"]
[White "fixture_a"]
[Black "fixture_b"]
[SetUp "1"]
[FEN "{FEN}"]
[Result "*"]

1. Re2 *
'''
    ingest_pgn(db, pgn)
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    return db


@pytest.mark.parametrize(
    "mate_ready,back_rank_ready",
    [((1, 2), ()), ((1, 2), (1,)), ((1,), ()), ((), ())],
)
def test_budget_mixed_replay_and_fresh_work_survives_restart(
    tmp_path, monkeypatch, mate_ready, back_rank_ready
):
    path = tmp_path / "budget.sqlite"
    db = two_decisions(path, monkeypatch)
    for position in mate_ready:
        process_mate(db, position, "fixture_a")
    for position in back_rank_ready:
        back_rank_auto.process_decision(db, position, "fixture_a")

    calls = []
    original = back_rank_auto._observe

    def observe(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(back_rank_auto, "_observe", observe)
    config = PipelineConfig(learner="fixture_a", mate_max_scan=10, mate_max_decisions=1)

    first = process_mates(db, config)
    assert first["status"] == "partial" and first["capped"]
    assert first["examined"] == 1 and first["back_rank"]["attempted"] == 1
    assert first["back_rank"]["attempt_limit"] == 1
    assert first["replayed"] == int(1 in mate_ready)
    assert first["back_rank"]["replayed"] == int(1 in back_rank_ready)
    assert len(calls) == int(1 not in back_rank_ready)

    db.connection.close()
    db = Database(path)
    second = process_mates(db, config)
    assert second["status"] == "complete" and not second["capped"]
    assert second["examined"] == 1 and second["back_rank"]["attempted"] == 1
    assert second["replayed"] == int(2 in mate_ready)
    assert second["back_rank"]["processed"] == 1
    assert len(calls) == int(1 not in back_rank_ready) + 1

    replay = process_mates(db, config)
    assert replay["capped"] and replay["replayed"] == 1
    assert replay["back_rank"]["replayed"] == 1 and replay["back_rank"]["processed"] == 0
    assert len(calls) == int(1 not in back_rank_ready) + 1


def test_failed_back_rank_attempt_consumes_budget_and_advances_cursor(tmp_path, monkeypatch):
    db = two_decisions(tmp_path / "failure.sqlite", monkeypatch)
    config = PipelineConfig(learner="fixture_a", mate_max_scan=10, mate_max_decisions=1)
    for position in (1, 2):
        process_mate(db, position, "fixture_a")

    original = back_rank_worker_item.process_decision

    def fail(*_args):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(back_rank_worker_item, "process_decision", fail)
    first = process_mates(db, config)
    assert first["status"] == "partial" and first["capped"]
    assert first["back_rank"]["attempted"] == first["back_rank"]["unavailable"] == 1
    assert first["back_rank"]["processed"] == 0
    monkeypatch.setattr(back_rank_worker_item, "process_decision", original)
    second = process_mates(db, config)
    assert second["examined"] == 1 and second["back_rank"]["processed"] == 1
    assert (
        db.connection.execute(
            "SELECT position_id FROM detector_runs WHERE producer='back-rank-observation'"
        ).fetchone()[0]
        == 2
    )
