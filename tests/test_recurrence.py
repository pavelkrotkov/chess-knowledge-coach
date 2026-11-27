"""Behavioral checks for bounded source-linked recurrence summaries."""

import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.recurrence_report import report
from chess_coach.web import create_app

START = "2026-10-01T00:00:00+00:00"
END = "2026-11-01T00:00:00+00:00"
PREV = "2026-09-01T00:00:00+00:00"


def game(day, moves="1. e4 e5 2. Nf3 Nc6 3. Bc4"):
    return f"""[Event "Synthetic"]
[White "Learner"]
[Black "Opponent"]
[UTCDate "2026.10.{day:02}"]
[UTCTime "12:00:00"]
[TimeControl "600+0"]
[WhiteElo "1500"]
[BlackElo "1600"]
[Result "*"]

{moves} *"""


def add(db, game_id, ply, outcome, *, subject="learner", version="1.0.1", observed=None):
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=?", (game_id, ply)
    ).fetchone()[0]
    fact = record_fact_run(
        db,
        position_id=position,
        producer="fork-opportunity",
        detector_version=version,
        input_data={"synthetic": True},
        facts=[{"fact_type": "fork_opportunity", "payload": {"kind": "fork", "outcome": outcome}}],
    )
    db.connection.execute("BEGIN IMMEDIATE")
    mapping = record_mapping_run_in_transaction(
        db,
        position_id=position,
        producer="fork-opportunity-mapper",
        mapper_version=version,
        subject=subject,
        operation="execute",
        scope_key="fork-v1",
        input_data={},
        mappings=[
            {
                "skill": "fork",
                "outcome": outcome,
                "confidence": 0.5,
                "fact_ids": fact["fact_ids"],
                "context": {},
                "observation_at": observed or f"2026-10-{game_id:02}T12:00:00+00:00",
            }
        ],
    )
    db.connection.commit()
    return mapping["evidence_ids"][0]


def test_recurrence_review_boundaries_and_independence(tmp_path, monkeypatch, capsys):
    path = tmp_path / "data.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, game(1, "1. e4 {[%clk 0:00:25]} e5 2. Nf3 Nc6 3. Bc4"))
    first = add(db, 1, 1, "failure")
    kept = add(db, 1, 3, "failure")
    current = report(db, "learner", START, END, PREV)
    group = current["current"][0]
    assert (group["misses"], group["miss_games"], group["games_with_repetitions"]) == (2, 1, 1)
    assert group["currentness"] == {"currentness unverified": 2}
    strata = {(item["field"], item["value"]): item for item in group["strata"]}
    assert strata[("clock", "unknown")]["misses"] == 1
    assert strata[("clock", "30 seconds or less")]["misses"] == 1
    assert strata[("opening familiarity", "unavailable")]["opportunities"] == 2
    ingest_pgn(db, game(2, "1. d4 {[%clk 0:05:00]} d5 2. Nf3 Nf6"))
    second = add(db, 2, 1, "failure")
    review_evidence(db, second, decision="accept", actor="synthetic")
    group = report(db, "learner", START, END, PREV)["current"][0]
    assert (group["misses"], group["miss_games"]) == (3, 2)
    assert group["review"] == {"unreviewed": 2, "accepted": 1}
    # Backfill can import older games later than the latest played games.
    ingest_pgn(db, game(2, "1. c4 e5"))
    ingest_pgn(db, game(1, "1. Nf3 d5"))
    undated = (
        game(3, "1. b3 e5")
        .replace('[UTCDate "2026.10.03"]\n', "")
        .replace('[UTCTime "12:00:00"]\n', "")
    )
    ingest_pgn(db, undated)
    ingest_pgn(db, game(3, "1. a3 d5").replace('[White "Learner"]', '[White "Other"]'))
    db.connection.execute("UPDATE style_game_times SET status='stale' WHERE game_id=6")
    for game_id, status in ((3, "complete"), (4, "pending")):
        db.connection.execute(
            """INSERT INTO pipeline_stages
            (game_id,stage,input_hash,status,detail,updated_at) VALUES (?,?,?,?,?,?)""",
            (game_id, "analysis", "fixture", status, "", "2026-10-03T00:00:00+00:00"),
        )
    db.connection.commit()
    monkeypatch.setattr("chess_coach.diagnostic_coverage.MAX_GAMES", 1)
    from chess_coach.coaching_report import report as coaching_report

    sample = report(db, "learner", START, END, PREV)
    coverage = sample["coverage"]
    assert coverage["analysis_stages"] == {"complete": 1}
    assert coverage["time_coverage"]["boundary_tie"]
    assert coverage["time_coverage"]["unknown_time_lower_bound"] == 1
    assert coverage["time_coverage"]["unknown_ownership_global_lower_bound"] == 1
    assert sample["current"][0]["misses"] == 3
    assert sample["recorded_mappings"][0]["rows"] == {"failure": 3}
    coaching = coaching_report(db, "learner")
    assert coaching["coverage"]["analysis_stages"] == {"complete": 1}
    assert coaching["coverage"]["database_games"] == 6
    assert coaching["coverage"]["database_analysis"] == {"complete": 1, "pending": 1}
    from chess_coach.diagnostic_coverage import diagnostic_coverage
    from chess_coach.recurrence_sources import games
    from chess_coach.style_time_projection import update_projection

    assert list(games(db, "learner")[0]) == [5, 4, 3, 2, 1]
    db.connection.execute(
        "UPDATE style_game_times SET started_at='2026-10-04T00:00:00+00:00' WHERE game_id=3"
    )
    invalid = diagnostic_coverage(db, "learner")
    assert invalid["examined_games"] == 0
    assert invalid["time_coverage"]["candidate_recheck_failed"] == 1
    update_projection(db.connection, 3)
    db.connection.commit()
    review_evidence(db, second, decision="revoke", actor="synthetic")
    group = report(db, "learner", START, END, PREV)["current"][0]
    assert group["miss_games"] == 1
    review_evidence(db, first, decision="reject", actor="synthetic")
    assert report(db, "learner", START, END, PREV)["current"][0]["misses"] == 1
    assert report(db, "other", START, END, PREV)["current"] == []
    with pytest.raises(ValueError):
        report(db, "learner", END, START, PREV)
    # Compare identical synthetic data through the existing broad and single-pair seams.
    broad, broad_work = measure_work(db, monkeypatch, selected=False)
    single, single_work = measure_work(db, monkeypatch, selected=True)
    landing_coverage, landing_work = measure_work(db, monkeypatch, selected="landing")
    assert landing_coverage["analysis_stages"] == {"complete": 1}
    assert landing_work["evidence_reads"] == landing_work["game_replays"] == 0
    assert landing_work["history_rebuilds"] == landing_work["lesson_builds"] == 0
    assert broad["current"] == single["current"] and broad["previous"] == single["previous"]
    assert broad_work["evidence_reads"] == 40 and single_work["evidence_reads"] == 2
    assert broad_work["game_replays"] == single_work["game_replays"] == 1
    assert broad_work["lesson_builds"] == single_work["lesson_builds"] == 1
    print(
        "synthetic_recurrence_work",
        {"broad": broad_work, "single": single_work, "landing": landing_work},
    )
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="synthetic",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    from html import unescape
    from urllib.parse import parse_qs, urlsplit

    import chess_coach.recurrence_web_report as web_report
    from chess_coach.recurrence_skills import PAIRS

    calls = []
    original_report = web_report.report

    def counted_report(*args, **kwargs):
        calls.append((kwargs.get("skill"), kwargs.get("operation")))
        return original_report(*args, **kwargs)

    monkeypatch.setattr(web_report, "report", counted_report)
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    dates = {"start": START, "end": END, "compare_start": PREV}
    landing = client.get(
        "/recurrence", query_string=dates, base_url="https://coach.invalid", headers=headers
    )
    assert landing.status_code == 200 and calls == []
    assert b"complete 1" in landing.data and b"Choose a pattern" in landing.data
    import re

    links = re.findall(r'href="([^"]+)"', unescape(landing.get_data(as_text=True)))
    pairs = set()
    for link in links:
        parts = urlsplit(link)
        query = parse_qs(parts.query)
        if parts.path == "/recurrence" and "skill" in query and "operation" in query:
            assert query["start"] == [START] and query["end"] == [END]
            assert query["compare_start"] == [PREV]
            pairs.add((query["skill"][0], query["operation"][0]))
    assert pairs == set(PAIRS)
    for skill, operation in PAIRS:
        response = client.get(
            "/recurrence",
            query_string={**dates, "skill": skill, "operation": operation},
            base_url="https://coach.invalid",
            headers=headers,
        )
        assert response.status_code == 200
    assert calls == list(PAIRS)
    response = client.get(
        "/recurrence",
        query_string={**dates, "skill": "fork", "operation": "execute"},
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert b"provisional recorded candidates" in response.data
    assert f"/evidence/{kept}".encode() in response.data and b"game 1, ply 3" in response.data
    assert f"/evidence/{first}".encode() not in response.data
    assert f"/evidence/{second}".encode() not in response.data
    assert (
        b"complete 1" in response.data
        and b"tie at the indexed sample boundary: True" in response.data
    )
    updated = Database(path)
    review_evidence(updated, kept, decision="accept", actor="synthetic")
    updated.close()
    assert (
        f"/evidence/{kept}".encode()
        in client.get(
            "/recurrence",
            query_string={**dates, "skill": "fork", "operation": "execute"},
            base_url="https://coach.invalid",
            headers=headers,
        ).data
    )
    updated = Database(path)
    review_evidence(updated, kept, decision="revoke", actor="synthetic")
    updated.close()
    revoked = client.get(
        "/recurrence",
        query_string={**dates, "skill": "fork", "operation": "execute"},
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert f"/evidence/{kept}".encode() not in revoked.data
    invalid = client.get(
        "/recurrence",
        query_string={"start": END, "end": START, "compare_start": PREV},
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert b"Report unavailable" in invalid.data
    coaching_page = app.test_client().get(
        "/coaching?full=1",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
    )
    assert coaching_page.status_code == 200
    assert (
        b"complete 1" in coaching_page.data
        and b"no verified start time: at least 1" in coaching_page.data
    )

    import json
    import sys

    from chess_coach.cli import main

    updated = Database(path)
    ample = add(updated, 2, 3, "failure")
    prior_pgn = game(2, "1. c4 e5").replace("2026.10.02", "2026.09.02")
    ingest_pgn(updated, prior_pgn)
    prior_game = updated.connection.execute(
        "SELECT id FROM games WHERE pgn=?", (prior_pgn,)
    ).fetchone()[0]
    prior = add(updated, prior_game, 1, "failure", observed="2026-09-02T12:00:00+00:00")
    comparison = report(updated, "learner", START, END, PREV, skill="fork", operation="execute")
    current_group = comparison["current"][0]
    previous_group = comparison["previous"][0]
    assert (current_group["independent_games"], previous_group["independent_games"]) == (1, 1)
    assert [item["id"] for item in current_group["examples"]] == [ample]
    assert [item["id"] for item in previous_group["examples"]] == [prior]
    assert any(
        item["field"] == "clock" and item["value"] == "over 30 seconds" and item["misses"] == 1
        for item in current_group["strata"]
    )
    updated.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "recurrence",
            "--learner",
            "learner",
            "--start",
            START,
            "--end",
            END,
            "--compare-start",
            PREV,
            "--skill",
            "fork",
            "--operation",
            "execute",
        ],
    )
    capsys.readouterr()
    main()
    cli = json.loads(capsys.readouterr().out)
    for period in ("current", "previous"):
        assert cli[period][0]["independent_games"] == comparison[period][0]["independent_games"]
        assert cli[period][0]["examples"] == comparison[period][0]["examples"]


def measure_work(db, monkeypatch, *, selected):
    import time

    import chess_coach.preview_history as preview_history_module
    import chess_coach.recurrence_collect as collect_module
    import chess_coach.recurrence_game_cache as cache_module
    import chess_coach.recurrence_report_helpers as helpers_module
    import chess_coach.recurrence_web_report as web_report
    from chess_coach.preview_snapshot import preview_history
    from chess_coach.recurrence_snapshot import read_snapshot

    counts = {"evidence_reads": 0, "game_replays": 0, "history_rebuilds": 0, "lesson_builds": 0}
    with monkeypatch.context() as patch:

        def wrap(module, name, metric):
            original = getattr(module, name)

            def counted(*args, **kwargs):
                counts[metric] += 1
                return original(*args, **kwargs)

            patch.setattr(module, name, counted)

        wrap(collect_module, "evidence", "evidence_reads")
        wrap(helpers_module, "evidence", "evidence_reads")
        wrap(cache_module, "load_game", "game_replays")
        wrap(preview_history_module, "decision_context_boards", "history_rebuilds")
        wrap(web_report, "build", "lesson_builds")
        start = time.perf_counter()
        if selected == "landing":
            result = web_report.landing(db, "learner", START, END, PREV)
        else:
            with read_snapshot(db), preview_history(db, "learner") as history:
                result = report(
                    db,
                    "learner",
                    START,
                    END,
                    PREV,
                    skill="fork" if selected else None,
                    operation="execute" if selected else None,
                    _history=history,
                )
                web_report._attach_lessons(result, db, "learner", history)
        counts["snapshot_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return result, counts


def test_duplicate_import_alias_and_replay_count_once(tmp_path):
    db = Database(tmp_path / "aliases.sqlite")
    db.initialize()
    pgn = game(1, "1. e4 e5")
    ingest_pgn(db, pgn, source="fixture-a")
    ingest_pgn(db, pgn, source="fixture-b")
    first = add(db, 1, 1, "failure")
    assert add(db, 1, 1, "failure") == first
    add(db, 2, 1, "failure", observed="2026-10-01T12:00:00+00:00")
    result = report(db, "learner", START, END, PREV)
    assert result["current"][0]["opportunities"] == 1
    assert result["current"][0]["independent_games"] == 1
    assert result["coverage"]["excluded"]["duplicate decision"] == 1

    from collections import Counter

    from chess_coach.preview_snapshot import preview_history
    from chess_coach.recurrence_game_cache import source as cached_game
    from chess_coach.recurrence_sources import load_game

    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=1"
    ).fetchone()[0]
    normal = load_game(db, "learner", 1)
    row = {"game_id": 1, "position_id": position}
    with preview_history(db, "learner") as history:
        history.targets([position])
        shared = cached_game(db, "learner", row, {}, {}, Counter(), _history=history)
        assert shared["key"] == normal["key"]
        for key, decision in shared["decisions"].items():
            assert {k: v for k, v in decision.items() if k != "processed_at"} == {
                k: v for k, v in normal["decisions"][key].items() if k != "processed_at"
            }
        assert len(history.games[1].entries) == 1
        assert "prompt_fen" not in history.context(1, position)
        board = history.board(1, position)
        original = history.board(1, position).fen()
        board.push(next(iter(board.legal_moves)))
        assert history.board(1, position).fen() == original
        with pytest.raises(ValueError):
            history.contexts(db, "other", 1, position)
        # A preview consumed before recurrence falls back to a complete replay.
        history.targets([position])
        history.board(1, position)
        assert not history.can_share(db, "learner", 1, position)
        fallback = cached_game(db, "learner", row, {}, {}, Counter(), _history=history)
        assert fallback["key"] == normal["key"]
        assert history.games[1].contexts is None
        history.targets([])
        assert not history.games
        with pytest.raises(ValueError):
            history.board(1, position)
    with pytest.raises(ValueError):
        history.contexts(db, "learner", 1, position)

    # Later corruption invalidates full-game recurrence even when an earlier board is legal.
    db.connection.execute("UPDATE positions SET uci='a1a1' WHERE game_id=1 AND ply=2")
    db.connection.commit()
    with preview_history(db, "learner") as history:
        history.targets([position])
        assert cached_game(db, "learner", row, {}, {}, Counter(), _history=history) is None
    db.close()
