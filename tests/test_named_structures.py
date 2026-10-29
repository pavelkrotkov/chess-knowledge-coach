"""Named structures are observations of pawn geometry, with atomic lineage."""

import json
import sys

import chess
import pytest

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.named_structure_report import structure_report
from chess_coach.named_structures import match_structures
from chess_coach.structures import extract_game_episodes
from chess_coach.web import create_app

IQP = "4k3/8/8/3p4/3P4/8/8/4K3 w - - 0 1"
CARLSBAD = "4k3/pp6/2p5/3p4/3P4/4P3/PP6/4K3 w - - 0 1"


def matches(fen):
    return {
        (item["family"], item["color"], item["square"])
        for item in match_structures(chess.Board(fen))
    }


def test_exact_matches_color_mirrors_overlaps_and_near_misses():
    assert matches(IQP) == {("iqp", "white", "d4"), ("iqp", "black", "d5")}
    assert matches(CARLSBAD) == {("carlsbad", "white", None)}
    mirrored = chess.Board(CARLSBAD).mirror().fen()
    assert matches(mirrored) == {("carlsbad", "black", None)}
    assert matches("4k3/pp6/2p5/3p4/3P4/2P1P3/PP6/4K3 w - - 0 1") == set()
    assert matches("4k3/pp6/8/2pp4/3P4/4P3/PP6/4K3 w - - 0 1") == set()
    assert matches("4k3/8/8/8/3P4/2P5/8/4K3 w - - 0 1") == set()


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


def test_cli_browser_and_source_link(setup, monkeypatch, capsys):
    path, db = setup
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "structure-history", "--learner", "learner"]
    )
    main()
    assert json.loads(capsys.readouterr().out) == structure_report(db, "learner")
    app = create_app(
        db_path=path,
        subject="learner",
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    assert client.get("/structures", base_url="https://coach.invalid").status_code == 403
    page = client.get("/structures", base_url="https://coach.invalid", headers=headers)
    assert b"Carlsbad" in page.data and b"Typical plans" in page.data
    assert (
        client.get(
            "/structures/positions/1", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/structures/positions/999", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )


def test_legal_transposition_and_timing_from_ingested_game():
    db = Database(":memory:")
    db.initialize()
    games = [
        '[White "Learner"]\n[Black "Opponent"]\n[Result "*"]\n[Opening "Synthetic label"]\n\n1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. cxd5 exd5 5. Bg5 Be7 6. e3 c6 *',
        '[White "Learner"]\n[Black "Opponent"]\n[Result "*"]\n[Opening "Different synthetic label"]\n\n1. d4 Nf6 2. c4 e6 3. Nc3 d5 4. cxd5 exd5 5. Bg5 Be7 6. e3 c6 *',
    ]
    for game in games:
        ingest_pgn(db, game)
    for game_id in (1, 2):
        extract_game_episodes(db, game_id)
    family = structure_report(db, "learner")["families"][1]
    assert family["games"] == 2
    assert [(item["start_ply"], item["end_ply"]) for item in family["items"]] == [
        (12, 12),
        (12, 12),
    ]
    assert all(item["episode_ids"] and item["position_id"] for item in family["items"])
