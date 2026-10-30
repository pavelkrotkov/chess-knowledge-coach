"""Named structures are observations of pawn geometry, with atomic lineage."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.named_structure_report import structure_report
from chess_coach.structures import extract_game_episodes

IQP = "4k3/8/8/3p4/3P4/8/8/4K3 w - - 0 1"
CARLSBAD = "4k3/pp6/2p5/3p4/3P4/4P3/PP6/4K3 w - - 0 1"


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "fixture.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(
        db,
        '[Event "Fixture"]\n[White "Learner"]\n[Black "Opponent"]\n[Result "*"]\n\n1. d4 d5 2. c4 e6 *',
    )
    positions = db.connection.execute("SELECT id FROM positions ORDER BY ply").fetchall()
    for row, fen in zip(positions, (CARLSBAD, CARLSBAD, IQP, IQP), strict=True):
        db.connection.execute("UPDATE positions SET fen=? WHERE id=?", (fen, row["id"]))
    db.connection.commit()
    extract_game_episodes(db, 1, detector_version="fixture-v1")
    return path, db


def test_history_transitions_replay_lineage_and_subject(setup):
    _, db = setup
    before = structure_report(db, "learner")
    assert before["games_examined"] == 1
    iqp, carlsbad = before["families"][:2]
    assert iqp["episodes"] == 2 and iqp["games"] == 1
    assert carlsbad["episodes"] == 1 and carlsbad["items"][0]["end_ply"] == 2
    assert all(
        item["episode_ids"] and item["run_id"]
        for family in before["families"]
        for item in family["items"]
    )
    extract_game_episodes(db, 1, detector_version="fixture-v1")
    assert structure_report(db, "learner") == before
    assert structure_report(db, "stranger")["games_examined"] == 0
    with pytest.raises(ValueError):
        structure_report(db, "default")
    extract_game_episodes(db, 1, detector_version="fixture-v2")
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 2
    assert (
        structure_report(db, "learner")["families"][1]["items"][0]["atomic_detector_version"]
        == "fixture-v2"
    )
