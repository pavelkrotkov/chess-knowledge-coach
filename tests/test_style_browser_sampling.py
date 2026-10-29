"""The private style page bounds work before source replay and states coverage."""

import json
import sys

import pytest

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.deep_execution_worker import run_deep
from chess_coach.ingest import ingest_pgn
from chess_coach.repertoire_sources import games_for_learner
from chess_coach.style_report import style_report
from chess_coach.style_sources import source_games
from chess_coach.web import create_app
from tests.test_deep_execution import options, prepare_selected, use_engine
from tests.test_deep_selection import LEARNER, PGN
from tests.test_style_choices import FourPlyEngine


def application(path):
    return create_app(
        db_path=path,
        subject=LEARNER,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )


def get(client, url):
    return client.get(
        url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "login"}
    )


def populated(path, count):
    db = Database(path)
    db.initialize()
    for number in range(count):
        ingest_pgn(db, PGN.replace("fixture_opponent", f"fixture_opponent{number}"))
    return db


def test_browser_caps_before_replay_and_cli_retains_default(tmp_path, monkeypatch, capsys):
    from chess_coach import style_game_sources, web_style

    path = tmp_path / "sample.sqlite"
    db = populated(path, 12)
    replay = style_game_sources.decisions_for_game
    replayed = []

    def observed(db, game_id, learner):
        replayed.append(game_id)
        return replay(db, game_id, learner)

    monkeypatch.setattr(style_game_sources, "decisions_for_game", observed)
    monkeypatch.setattr(web_style, "database", lambda: db)
    app = application(path)
    db.connection.execute("PRAGMA query_only = ON")
    before = db.connection.total_changes
    page = get(app.test_client(), "/style-choices?games=100")
    assert page.status_code == 200
    assert replayed == list(range(12, 2, -1))
    assert db.connection.total_changes == before
    assert b"Requested sample 10 attributable records; effective maximum 10" in page.data
    assert b"Sample truncated True" in page.data
    assert b"Decisions in unprocessed or suppressed records unknown True" in page.data
    assert b"not game chronology" in page.data
    assert b"games_without_selection" in page.data

    replayed.clear()
    sample = source_games(db, LEARNER, max_games=10)
    assert replayed == list(range(12, 2, -1))
    assert sample["independent_games"] == 10
    assert sample["omitted_attributable_games_lower_bound"] == 1
    assert sample["omitted_attributable_games_unknown"]
    assert sample["familiarity_history_incomplete"]
    assert all(
        context["familiarity"] == "unknown"
        and context["earlier_started_games_with_position"] is None
        for row in sample["games"]
        for context in row["contexts"]
    )

    replayed.clear()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert replayed == list(range(12, 0, -1))
    assert cli["coverage"]["requested_game_limit"] == 100
    assert cli["coverage"]["effective_game_limit"] == 100
    assert cli["coverage"]["examined_games"] == 12
    assert not cli["coverage"]["sample_truncated"]
    assert not cli["coverage"]["omitted_attributable_games_unknown"]
    assert cli["selection_counts"]["games_without_selection"] == 12
    db.close()


@pytest.mark.parametrize("invalid", [0, 101, -1, True, 1.5, "10"])
def test_sample_limit_is_validated(invalid):
    db = Database(":memory:")
    db.initialize()
    with pytest.raises(ValueError):
        games_for_learner(db, LEARNER, limit=invalid)
    db.close()


def test_scan_exhaustion_is_unknown_not_zero(tmp_path, monkeypatch):
    from chess_coach import repertoire_sources

    db = populated(tmp_path / "scan.sqlite", 1)
    for number in range(2):
        pgn = PGN.replace("fixture_learner", f"unrelated_white{number}").replace(
            "fixture_opponent", f"unrelated_black{number}"
        )
        ingest_pgn(db, pgn)
    monkeypatch.setattr(repertoire_sources, "MAX_SCAN", 2)
    report = style_report(db, LEARNER, max_games=10)
    coverage = report["coverage"]
    assert coverage["examined_games"] == 0
    assert coverage["scan_limit_reached"] and coverage["sample_truncated"]
    assert coverage["omitted_attributable_games_lower_bound"] == 0
    assert coverage["omitted_attributable_games_unknown"]
    assert coverage["unprocessed_decisions_unknown"]
    db.close()


def test_source_and_related_practice_navigation_remain_available(tmp_path, monkeypatch):
    path = tmp_path / "source.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=6)
    use_engine(monkeypatch, FourPlyEngine(db))
    run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=6))
    report = style_report(db, LEARNER, max_games=10)
    assert report["observations"]
    position_id = report["observations"][0]["position_id"]
    db.close()
    client = application(path).test_client()
    page = get(client, "/style-choices")
    assert page.status_code == 200 and f"/decisions/{position_id}".encode() in page.data
    decision = get(client, f"/decisions/{position_id}")
    assert decision.status_code == 200
    assert f"/decisions/{position_id}/related-captures".encode() in decision.data
    practice = get(client, f"/decisions/{position_id}/related-captures")
    assert practice.status_code in (200, 400)
    if practice.status_code == 400:
        assert b"No current supported capture observation" in practice.data
