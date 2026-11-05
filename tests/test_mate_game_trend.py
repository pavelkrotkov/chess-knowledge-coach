"""Complete mate-in-one cohorts, provenance, and coverage gates."""

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.mate_game_trend import report
from chess_coach.style_time_projection import update_projection
from chess_coach.web import create_app
from tests.test_mate_proof import FEN


def pgn(second, move, event="Synthetic", dated=True):
    date = f'[UTCDate "2026.01.01"]\n[UTCTime "00:00:{second:02}"]\n' if dated else ""
    return f'''[Event "{event}"]
[White "fixture_a"]
[Black "fixture_b"]
{date}[SetUp "1"]
[FEN "{FEN}"]
[Result "1-0"]

1. {move} 1-0
'''


def test_complete_private_samples_and_unavailable_coverage(tmp_path):
    path = tmp_path / "games.sqlite"
    db = Database(path)
    db.initialize()
    for i in range(41):
        ingest_pgn(db, pgn(i, "Qg1" if i % 2 else "Qg7#"))
    ingest_pgn(db, pgn(40, "Qg7#", event="Duplicate import"))
    before = db.connection.total_changes
    result = report(db, "fixture_a")
    assert db.connection.total_changes == before
    assert result["comparable"]
    assert result["duplicates"] == 1 and result["unavailable"] == 0
    assert result["newer"]["games"] == result["earlier"]["games"] == 20
    assert result["newer"]["opportunities"] == result["earlier"]["opportunities"] == 20
    assert result["newer"]["misses"] == result["earlier"]["misses"] == 10
    assert result["newer"]["miss_games"] == 10
    assert result["newer"]["newest"].startswith("2026-01-01T00:00:40")
    assert result["earlier"]["oldest"].startswith("2026-01-01T00:00:01")

    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    url = "/game-samples/mate-in-one"
    assert client.get(url, base_url="https://coach.invalid").status_code == 403
    page = client.get(
        url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert page.status_code == 200 and b"10 missed of 20" in page.data
    assert b"/decisions/" in page.data and b"practice attempts are not included" in page.data
    assert b"fixture_a" not in page.data and b"fixture_b" not in page.data
    inspection = client.get(
        "/games/1/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert inspection.status_code == 200
    assert b"1 eligible turns; 1 fully checked" in inspection.data
    assert b"immediate mate" in inspection.data and b"miss rate is unavailable" in inspection.data
    app.config["SUBJECT"] = "fixture_c"
    assert (
        client.get(
            "/games/1/short-mate",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        ).status_code
        == 400
    )
    app.config["SUBJECT"] = "default"
    unavailable = client.get(
        url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert unavailable.status_code == 400 and b"Learner identity is unavailable" in unavailable.data
    app.config["SUBJECT"] = "fixture_a"

    ingest_pgn(db, pgn(0, "Qg1", event="Unknown date", dated=False))
    uncertain = report(db, "fixture_a")
    assert not uncertain["comparable"]
    assert uncertain["coverage"]["unknown_time_lower_bound"] == 1

    db.connection.execute("DELETE FROM games WHERE id=(SELECT MAX(id) FROM games)")
    db.connection.commit()
    game = db.connection.execute("SELECT id,pgn FROM games WHERE pgn LIKE '%00:00:20%'").fetchone()
    db.connection.execute(
        "UPDATE games SET pgn=? WHERE id=?",
        (game["pgn"].replace("00:00:20", "00:00:21"), game["id"]),
    )
    update_projection(db.connection, game["id"])
    db.connection.commit()
    assert not report(db, "fixture_a")["comparable"]
    db.close()


def test_unfinished_and_automatic_terminal_games_are_unavailable(tmp_path):
    from chess_coach.mate_game_sample import prepared_game

    db = Database(tmp_path / "unfinished.sqlite")
    db.initialize()
    unfinished = pgn(1, "Qg1").replace("1-0", "*")
    ingest_pgn(db, unfinished)
    game = db.connection.execute("SELECT * FROM games").fetchone()
    import pytest

    with pytest.raises(ValueError, match="unfinished"):
        prepared_game(db, game, "fixture_a")
    db.close()

    db = Database(tmp_path / "terminal.sqlite")
    db.initialize()
    ingest_pgn(db, pgn(1, "Qg1").replace("0 1", "150 1"))
    game = db.connection.execute("SELECT * FROM games").fetchone()
    with pytest.raises(ValueError, match="game termination"):
        prepared_game(db, game, "fixture_a")
    db.close()


def test_result_contradicting_checkmate_is_unavailable(tmp_path):
    import pytest

    from chess_coach.mate_game_sample import prepared_game

    db = Database(tmp_path / "contradiction.sqlite")
    db.initialize()
    ingest_pgn(db, pgn(1, "Qg7#").replace("1-0", "0-1"))
    game = db.connection.execute("SELECT * FROM games").fetchone()
    with pytest.raises(ValueError, match="contradicts"):
        prepared_game(db, game, "fixture_a")
    db.close()
