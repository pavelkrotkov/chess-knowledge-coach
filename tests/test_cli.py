import json
import sys

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
