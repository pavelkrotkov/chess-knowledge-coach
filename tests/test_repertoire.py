"""Behavioral coverage of the private, descriptive repertoire."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.openings import import_openings
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import game_input
from chess_coach.pipeline_opening import run_opening
from chess_coach.repertoire import game_detail, repertoire_report
from chess_coach.repertoire_sources import games_for_learner
from chess_coach.web import create_app


def game(white, black, moves, result="1-0", *, second=None):
    timestamp = (
        f'[UTCDate "2026.01.01"]\n[UTCTime "00:00:{second:02}"]\n' if second is not None else ""
    )
    return f'''{timestamp}[Event "Fixture"]
[White "{white}"]
[Black "{black}"]
[Result "{result}"]
[TimeControl "600+0"]
[WhiteElo "1500"]
[BlackElo "1600"]

{moves} {result}
'''


def test_repertoire_transpositions_colors_refresh_and_privacy(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite"
    db = Database(path)
    db.initialize()
    for text in (
        game("Learner", "Opponent", "1. d4 d5 2. Nf3 Nf6", second=3),
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5", "0-1", second=3),
        game("Opponent", "Learner", "1. d4 d5 2. Nf3 Nf6", second=2),
        game("Other", "Opponent", "1. d4 d5 2. Nf3 Nf6", second=6),
        game("Learner", "Opponent", "1. e4 e5", "*", second=1),
        game("Learner", "Opponent", "1. c4 e5"),
        game("Learner", "Opponent", "1. Nf3 d5", second=70),
    ):
        ingest_pgn(db, text)
    source = tmp_path / "opening.tsv"
    source.write_text("eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\n")
    import_openings(db, source, version="test", source_url="cc0://test")
    config = PipelineConfig(
        learner="learner",
        opening_version="test",
        opening_source="cc0://test",
        classifier_version="1.1.0",
    )
    for game_id in (1, 2, 3, 5):
        assert run_opening(db, game_id, game_input(db, game_id), config)["status"] == "complete"
    db.connection.execute("UPDATE style_game_times SET status='stale' WHERE game_id=4")
    report = repertoire_report(db, "learner")
    assert [g["id"] for g in report["games"]] == [2, 1, 3, 5]
    assert report["games"][0]["played_at"] == "2026-01-01T00:00:03+00:00"
    assert report["games"][0]["date"] == game_detail(db, "learner", 2)["date"]
    assert report["unknown"] == 1
    assert report["time_coverage"]["unknown_time_lower_bound"] == 2
    assert report["time_coverage"]["unknown_ownership_global_lower_bound"] == 1
    assert [row["id"] for row, _ in games_for_learner(db, "learner")[0]] == [7, 6, 5, 3, 2, 1]
    monkeypatch.setattr("chess_coach.repertoire.MAX_GAMES", 1)
    limited = repertoire_report(db, "learner")
    assert [g["id"] for g in limited["games"]] == [2]
    assert limited["game_limit_reached"] and limited["time_coverage"]["boundary_tie"]
    monkeypatch.undo()
    white = next(g for g in report["groups"] if g["color"] == "white" and len(g["lines"]) == 2)
    assert white["count"] == 2 and len(white["lines"]) == 2
    assert white["outcomes"] == {"win": 1, "loss": 1}
    black = next(g for g in report["groups"] if g["color"] == "black" and g["names"])
    assert black["count"] == 1 and black["outcomes"] == {"loss": 1}
    assert game_detail(db, "learner", 1)["learner_rating"] == 1500
    with pytest.raises(ValueError, match="unavailable"):
        game_detail(db, "learner", 4)
    source.write_text("eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\nC20\tNew\te4 e5\n")
    import_openings(db, source, version="test", source_url="cc0://test")
    assert repertoire_report(db, "learner")["stale"] == 4
    assert run_opening(db, 5, game_input(db, 5), config)["status"] == "complete"
    assert game_detail(db, "learner", 5)["opening"]["name"] == "New"
    assert (
        db.connection.execute("SELECT COUNT(*) FROM opening_runs WHERE game_id=5").fetchone()[0]
        == 2
    )
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/repertoire", base_url="https://coach.invalid").status_code == 403
    headers = {"Tailscale-User-Login": "login"}
    response = client.get("/repertoire", base_url="https://coach.invalid", headers=headers)
    assert response.status_code == 200
    assert b"New" in response.data and b"/repertoire/games/5" in response.data
    assert b"Structure coverage:" in response.data
    assert response.data.count(b"played 2026-01-01T00:00:01+00:00") >= 2
    assert b"Games with known ownership and no verified start time: at least 2" in response.data
    assert (
        client.get(
            "/repertoire/games/1", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/repertoire/games/4", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )
