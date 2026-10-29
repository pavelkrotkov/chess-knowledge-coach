"""Interrupted tactical generations are isolated from other fact producers."""

import time

import pytest

from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.pipeline_generation_state import superseded
from tests.test_pipeline import game, setup


@pytest.mark.parametrize("table", ["detector_runs", "mapping_runs"])
@pytest.mark.parametrize("foreign", [False, True])
def test_tactical_generation_is_scoped_to_its_producer(tmp_path, monkeypatch, table, foreign):
    db, _, _, _ = setup(tmp_path, monkeypatch, count=0)
    ingest_pgn(db, game("fixture99", int(time.time()) - 5))
    if table == "detector_runs":
        for version in ("first", "second"):
            record_fact_run(
                db,
                position_id=1,
                producer="fixture-other" if foreign else "mate-in-one",
                detector_version=version,
                input_data={"pipeline_generation": 1},
                facts=[],
            )
    else:
        for version in ("first", "second"):
            with mapping_transaction(db):
                record_mapping_run_in_transaction(
                    db,
                    position_id=1,
                    producer="fixture-other-mapper" if foreign else "mate-in-one-mapper",
                    mapper_version=version,
                    subject="learner",
                    operation="execute",
                    scope_key="fixture",
                    input_data={"pipeline_generation": 1},
                    mappings=[],
                )
    assert (
        db.connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE status=?", ("superseded",)
        ).fetchone()[0]
        == 1
    )
    assert superseded(db.connection, 1, "tactical", 1) is (not foreign)
