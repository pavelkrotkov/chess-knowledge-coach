import json
import sys

import pytest

from chess_coach.cli import main


def test_cli_initializes_ingests_and_queries_puzzles(tmp_path, monkeypatch, capsys):
    db = tmp_path / "coach.sqlite"
    pgn = tmp_path / "game.pgn"
    pgn.write_text('[Event "CLI"]\n[White "A"]\n[Black "B"]\n[Result "*"]\n\n1. e4 *\n')
    puzzles = tmp_path / "puzzles.csv"
    puzzles.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Themes\n"
        "p1,fen,e2e4,1200,80,fork\n"
        "p2,fen,d2d4,1800,60,mate\n"
    )

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(db), *args])
        main()
        return capsys.readouterr().out

    assert run("init-db") == f"initialized {db}\n"
    assert json.loads(run("ingest-pgn", str(pgn))) == {"games": 1, "positions": 1}
    assert json.loads(run("import-puzzles", str(puzzles), "--version", "v1")) == {"rows": 2}
    rows = json.loads(run("query-puzzles", "--version", "v1", "--theme", "fork", "--limit", "1"))
    assert [row["puzzle_id"] for row in rows] == ["p1"]
    assert rows[0]["objective"] == "execute"
    assert json.loads(run("evidence-report")) == []


def test_sync_lichess_dispatch_forwards_options_and_token(tmp_path, monkeypatch, capsys):
    from chess_coach import cli_commands_games

    class Client:
        def __init__(self, *, token):
            assert token == "test-token"

        def sync_user(self, db, username, *, max_games, page_size, since):
            assert (username, max_games, page_size, since) == ("user", 7, 3, 42)
            return {"games": 2, "positions": 9}

    monkeypatch.setenv("LICHESS_API_TOKEN", "test-token")
    monkeypatch.setattr(cli_commands_games, "LichessClient", Client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(tmp_path / "coach.sqlite"),
            "sync-lichess",
            "user",
            "--max-games",
            "7",
            "--page-size",
            "3",
            "--since",
            "42",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out) == {"games": 2, "positions": 9}


def test_parser_rejects_invalid_choices_without_creating_database(tmp_path, monkeypatch, capsys):
    db = tmp_path / "unused.sqlite"
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(db), "review-training", "1", "bad"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "invalid choice: 'bad'" in capsys.readouterr().err
    assert not db.exists()
