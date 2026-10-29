"""Sicilian-family matches are overlapping observations of pawn geometry."""

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

HEDGEHOG = (
    "1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. c4 Nf6 "
    "6. Nc3 d6 7. Be2 b6 8. O-O Be7 9. Be3 Bb7 10. f3 O-O "
    "11. Qd2 Nbd7 12. Rfd1 Qc7 13. Rac1 d5"
)
TRANSPOSED = "1. c4 c5 2. Nf3 e6 3. e4 a6 4. d4 cxd4 5. Nxd4 Nf6 6. Nc3 d6 7. Be2 b6 8. O-O e5"
SCHEVENINGEN = "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 e6"
ENGLISH = "1. c4 c5 2. Nf3 e6 3. g3 Nf6 4. Bg2 a6 5. O-O b6 6. d4 cxd4 7. Nxd4 d6"


def game(moves):
    return f'[White "Learner"]\n[Black "Opponent"]\n[Opening "Unrelated fixture"]\n[Result "*"]\n\n{moves} *'


def recorded_game(db, moves):
    ingest_pgn(db, game(moves))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    extract_game_episodes(db, game_id)
    return game_id


def position(db, game_id, ply):
    fen = db.connection.execute(
        "SELECT fen FROM positions WHERE game_id=? AND ply=?", (game_id, ply)
    ).fetchone()["fen"]
    return chess.Board(fen)


def labels(board, version="1.2.0"):
    return {(m["family"], m["color"]) for m in match_structures(board, version=version)}


def family(report, name):
    return next(item for item in report["families"] if item["family"] == name)


def test_legal_overlaps_mirrors_near_misses_and_versions():
    db = Database(":memory:")
    db.initialize()
    hedge = recorded_game(db, HEDGEHOG)
    typical = position(db, hedge, 14)
    assert typical.is_valid() and typical.mirror().is_valid()
    all_three = {("maroczy", "white"), ("hedgehog", "black"), ("sicilian_scheveningen", "black")}
    assert labels(typical) == all_three
    assert labels(typical.mirror()) == {
        ("maroczy", "black"),
        ("hedgehog", "white"),
        ("sicilian_scheveningen", "white"),
    }
    assert not labels(typical, "1.1.0")
    assert not labels(typical, "1.0.0")
    before_bind = position(db, hedge, 8)
    assert ("maroczy", "white") not in labels(before_bind)
    broken = position(db, hedge, 26)
    assert not labels(broken) & all_three
    no_b6 = position(db, hedge, 13)
    assert ("hedgehog", "black") not in labels(no_b6)
    schev = recorded_game(db, SCHEVENINGEN)
    assert labels(position(db, schev, 10)) == {("sicilian_scheveningen", "black")}
    boles = recorded_game(db, SCHEVENINGEN + " 6. Be2 e5")
    assert labels(position(db, boles, 12)) == {("sicilian_boleslavsky", "black")}
    assert labels(position(db, boles, 12).mirror()) == {("sicilian_boleslavsky", "white")}
    english = recorded_game(db, ENGLISH)
    assert labels(position(db, english, 14)) == {("hedgehog", "black")}


def test_precise_exclusions_doubled_or_missing_pawns():
    db = Database(":memory:")
    db.initialize()
    game_id = recorded_game(db, HEDGEHOG)
    board = position(db, game_id, 14)
    board.remove_piece_at(chess.C4)
    assert ("maroczy", "white") not in labels(board)
    assert ("hedgehog", "black") in labels(board)
    board = position(db, game_id, 14)
    board.set_piece_at(chess.C6, chess.Piece(chess.PAWN, chess.BLACK))
    assert not labels(board) & {
        ("maroczy", "white"),
        ("hedgehog", "black"),
        ("sicilian_scheveningen", "black"),
    }
    board = position(db, game_id, 14)
    board.set_piece_at(chess.E3, chess.Piece(chess.PAWN, chess.WHITE))
    assert ("maroczy", "white") not in labels(board)
    assert ("sicilian_scheveningen", "black") not in labels(board)


def test_legal_transpositions_transformations_history_and_replay():
    db = Database(":memory:")
    db.initialize()
    first = recorded_game(db, HEDGEHOG)
    second = recorded_game(db, TRANSPOSED)
    assert position(db, first, 14).board_fen() == position(db, second, 14).board_fen()
    report = structure_report(db, "learner")
    expected = (("maroczy", 9), ("sicilian_scheveningen", 12), ("hedgehog", 14))
    for name, start in expected:
        entry = family(report, name)
        assert entry["games"] == 2
        item = next(item for item in entry["items"] if item["game_id"] == first)
        assert (item["start_ply"], item["end_ply"]) == (start, 25)
        assert item["episode_ids"] and item["run_id"] and item["position_id"]
    boles = family(report, "sicilian_boleslavsky")
    assert boles["games"] == 1
    assert (boles["items"][0]["start_ply"], boles["items"][0]["end_ply"]) == (16, 16)
    second_hedge = next(
        item for item in family(report, "hedgehog")["items"] if item["game_id"] == second
    )
    assert (second_hedge["start_ply"], second_hedge["end_ply"]) == (14, 15)
    second_bind = next(
        item for item in family(report, "maroczy")["items"] if item["game_id"] == second
    )
    assert second_bind["end_ply"] == 16
    extract_game_episodes(db, first)
    assert structure_report(db, "learner") == report
    for version, count in (("1.0.0", 2), ("1.1.0", 5)):
        old = structure_report(db, "learner", version=version)
        assert old["version"] == version and len(old["families"]) == count
    with pytest.raises(ValueError):
        structure_report(db, "learner", version="bad")


def test_cli_browser_previous_versions_and_source_links(tmp_path, monkeypatch, capsys):
    path = tmp_path / "fixture.sqlite"
    db = Database(path)
    db.initialize()
    recorded_game(db, HEDGEHOG)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "structure-history",
            "--learner",
            "learner",
            "--matcher-version",
            "1.1.0",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out) == structure_report(db, "learner", version="1.1.0")
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
    page = client.get("/structures", base_url="https://coach.invalid", headers=headers)
    assert b"Hedgehog-like" in page.data and b"1.2.0" in page.data
    assert b"source position" in page.data and b"do not identify the actual opening" in page.data
    old = client.get("/structures?version=1.1.0", base_url="https://coach.invalid", headers=headers)
    assert b"Hedgehog-like" not in old.data and b"French-like" in old.data
