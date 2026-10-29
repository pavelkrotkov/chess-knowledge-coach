"""Closed-center skeletons are geometry, not opening or skill conclusions."""

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

OVERLAP = "4k3/pp3ppp/2p1p3/3pP3/3P4/8/PPP2PPP/4K3 w - - 0 1"
BENONI = "4k3/pp3ppp/3p4/2pP4/4P3/8/PP3PPP/4K3 w - - 0 1"


def labels(board, version="1.1.0"):
    return {(m["family"], m["color"]) for m in match_structures(board, version=version)}


def test_matches_overlap_mirrors_and_prior_version():
    board = chess.Board(OVERLAP)
    assert labels(board) == {("french_advance", "white"), ("caro_advance", "white")}
    assert labels(board.mirror()) == {("french_advance", "black"), ("caro_advance", "black")}
    assert labels(board, "1.0.0") == set()
    board = chess.Board(BENONI)
    assert labels(board) == {("benoni", "white")}
    assert labels(board.mirror()) == {("benoni", "black")}
    assert labels(board, "1.0.0") == set()
    with pytest.raises(ValueError, match="unknown"):
        match_structures(board, version="0")


def test_missing_or_extra_pawns_do_not_create_skeletons():
    board = chess.Board(OVERLAP)
    board.remove_piece_at(chess.E6)
    assert not labels(board)
    board = chess.Board(OVERLAP)
    board.remove_piece_at(chess.C6)
    board.set_piece_at(chess.C5, chess.Piece(chess.PAWN, chess.BLACK))
    assert labels(board) == {("french_advance", "white")}
    board = chess.Board(OVERLAP)
    board.set_piece_at(chess.D3, chess.Piece(chess.PAWN, chess.WHITE))
    assert not labels(board)
    board = chess.Board(BENONI)
    board.remove_piece_at(chess.C5)
    assert ("benoni", "white") not in labels(board)
    assert ("iqp", "black") in labels(board)
    board = chess.Board(BENONI)
    board.set_piece_at(chess.E6, chess.Piece(chess.PAWN, chess.BLACK))
    assert not labels(board)


def family(report, name):
    return next(entry for entry in report["families"] if entry["family"] == name)


def game(moves, label):
    return f'[White "Learner"]\n[Black "Opponent"]\n[Opening "{label}"]\n[Result "*"]\n\n{moves} *'


def test_legal_transpositions_timing_transformations_and_lineage():
    db = Database(":memory:")
    db.initialize()
    games = (
        game("1. e4 c6 2. d4 d5 3. e5 Bf5 4. Nf3 e6 5. Be2 c5", "French fiction"),
        game("1. d4 c6 2. e4 d5 3. e5 Bf5 4. Nf3 e6", "Unrelated fiction"),
        game("1. d4 Nf6 2. c4 c5 3. d5 e6 4. Nc3 exd5 5. cxd5 d6 6. e4", "Synthetic"),
        game("1. d4 Nf6 2. c4 e6 3. Nc3 c5 4. d5 exd5 5. cxd5 d6 6. e4", "Different"),
    )
    for pgn in games:
        ingest_pgn(db, pgn)
    for game_id in range(1, 5):
        extract_game_episodes(db, game_id)
    # Each pair reaches the same pawn placement despite different move orders.
    fens = [
        db.connection.execute(
            "SELECT fen FROM positions WHERE game_id=? AND ply=?", (game_id, ply)
        ).fetchone()["fen"]
        for game_id, ply in ((1, 8), (2, 8), (3, 11), (4, 11))
    ]
    assert chess.Board(fens[0]).board_fen() == chess.Board(fens[1]).board_fen()
    assert chess.Board(fens[2]).board_fen() == chess.Board(fens[3]).board_fen()
    report = structure_report(db, "learner")
    french, caro, benoni = (
        family(report, name) for name in ("french_advance", "caro_advance", "benoni")
    )
    assert french["games"] == caro["games"] == benoni["games"] == 2
    first_french = next(item for item in french["items"] if item["game_id"] == 1)
    first_caro = next(item for item in caro["items"] if item["game_id"] == 1)
    assert (first_french["start_ply"], first_french["end_ply"]) == (8, 10)
    assert (first_caro["start_ply"], first_caro["end_ply"]) == (5, 9)
    assert all((item["start_ply"], item["end_ply"]) == (11, 11) for item in benoni["items"])
    assert all(
        item["episode_ids"] and item["run_id"] and item["position_id"]
        for entry in (french, caro, benoni)
        for item in entry["items"]
    )
    assert structure_report(db, "learner") == report
    old = structure_report(db, "learner", version="1.0.0")
    assert old["version"] == "1.0.0"
    assert [entry["family"] for entry in old["families"]] == ["iqp", "carlsbad"]


def test_cli_and_private_browser_offer_previous_matcher(tmp_path, monkeypatch, capsys):
    path = tmp_path / "fixture.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, game("1. e4 e6 2. d4 d5 3. e5 c5", "Synthetic"))
    extract_game_episodes(db, 1)
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
            "1.0.0",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out) == structure_report(db, "learner", version="1.0.0")
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
    assert b"French-like" in page.data and b"do not identify the actual opening" in page.data
    old = client.get("/structures?version=1.0.0", base_url="https://coach.invalid", headers=headers)
    assert b"1.0.0" in old.data and b"French-like" not in old.data
    assert (
        client.get(
            "/structures?version=invalid", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 400
    )
