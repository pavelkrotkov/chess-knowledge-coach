"""Complete mate-in-one cohorts, provenance, and coverage gates."""

import pytest

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
    assert (
        client.get(
            "/games/9223372036854775808/short-mate",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        ).status_code
        == 400
    )
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


def test_short_mate_background_samples_resume_and_detect_changes(tmp_path, monkeypatch):
    # A real bounded in-memory cohort resumes and withholds only a changed game.
    import sqlite3
    import sys
    from copy import deepcopy
    from types import SimpleNamespace

    import chess.engine

    from chess_coach import protection_game_current as protection_current
    from chess_coach import protection_game_report as protection_report
    from chess_coach import protection_game_worker as protection_worker
    from chess_coach import short_mate_trend_paths as mate_paths
    from chess_coach import short_mate_trend_scan as scan
    from chess_coach import short_mate_trend_select as selection
    from chess_coach import short_mate_trend_turns as turns
    from chess_coach import web_short_mate_game as protection_web
    from chess_coach.capabilities import capability_report
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.short_mate_trend_cohort import signature as source_signature
    from chess_coach.short_mate_trend_paths import binding, location
    from chess_coach.short_mate_trend_report import report as cached_report
    from chess_coach.short_mate_trend_select import _item
    from chess_coach.short_mate_trend_store import read, write
    from tests.test_pipeline import FakeEngine

    with monkeypatch.context() as patch:
        games_db = Database(":memory:")
        games_db.initialize()
        patch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: FakeEngine())
        config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
        for index in range(3):
            ingest_pgn(games_db, pgn(index, "Qg1"))
            assert (
                run_analysis(
                    games_db,
                    index + 1,
                    game_input(games_db, index + 1),
                    config,
                    engine_identity(sys.executable),
                )["status"]
                == "complete"
            )
        # A real owned analyzed decision proves a royal skewer without a miss claim.
        skewer_db = Database(":memory:")
        skewer_db.initialize()
        skewer_pgn = """[Event "Skewer"]
[White "fixture_a"]
[Black "fixture_b"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:00"]
[SetUp "1"]
[FEN "4q3/8/8/4k3/8/8/R7/7K w - - 0 1"]
[Result "1-0"]

1. Re2+ Kd6 1-0
"""
        ingest_pgn(skewer_db, skewer_pgn)
        assert (
            run_analysis(
                skewer_db, 1, game_input(skewer_db, 1), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
        with patch.context() as skewer_patch:
            skewer_patch.setattr(protection_web, "database", lambda: skewer_db)
            app = create_app(
                db_path=":memory:",
                subject="fixture_a",
                actor="operator",
                corpus="test",
                login="fixture",
                origin="https://coach.invalid",
            )
            client = app.test_client()
            url = "/decisions/1/skewer"
            assert client.get(url, base_url="https://coach.invalid").status_code == 403
            client.environ_base["HTTP_TAILSCALE_USER_LOGIN"] = "fixture"
            before = skewer_db.connection.total_changes
            page = client.get(url, base_url="https://coach.invalid")
            assert page.status_code == 200 and b"Your recorded move Re2+" in page.data
            assert b"queen on e8" in page.data and b"Rxe8" in page.data
            assert b"6 legal replies" in page.data and b"not a verdict" in page.data
            assert skewer_db.connection.total_changes == before
            from chess_coach import skewer_game_report as skewer_report

            ticks = [0]
            recheck = skewer_report.recheck

            def slow_recheck(*args):
                recheck(*args)
                ticks[0] = 4

            with skewer_patch.context() as timing:
                timing.setattr(skewer_report, "recheck", slow_recheck)
                late = skewer_report.report(skewer_db, "fixture_a", 1, clock=lambda: ticks[0])
                assert late["proof"] is None and late["reason"] == "time limit"
            app.config["SUBJECT"] = "fixture_b"
            assert client.get(url, base_url="https://coach.invalid").status_code == 400
            app.config["SUBJECT"] = "fixture_a"
            skewer_db.connection.execute(
                "UPDATE pipeline_stages SET status='failed' WHERE game_id=1 AND stage='analysis'"
            )
            skewer_db.connection.commit()
            assert client.get(url, base_url="https://coach.invalid").status_code == 400
        import time

        import chess

        from chess_coach.skewer_game_geometry import rear as skewer_rear
        from chess_coach.skewer_game_line import witness as skewer_witness
        from chess_coach.skewer_game_proof import inspect as inspect_skewer

        # The defender can claim a draw by choosing a 100th halfmove.
        draw_board = chess.Board("4q3/8/8/4k3/8/8/R7/7K w - - 98 1")
        checking = chess.Move.from_uci("a2e2")
        after, (target, piece) = skewer_rear(draw_board, checking)
        assert after.halfmove_clock == 99 and after.can_claim_fifty_moves()
        assert (
            skewer_witness(
                draw_board, checking, after, target, piece, time.monotonic() + 1, time.monotonic
            )
            is None
        )

        harmless = chess.Board("8/8/8/4k3/8/8/R7/7K w - - 0 1")
        assert inspect_skewer(harmless, "a2e2", time.monotonic() + 1, time.monotonic)[0] is None
        block = chess.Board("4q3/8/3n4/4k3/8/8/R7/7K w - - 0 1")
        assert inspect_skewer(block, "a2e2", time.monotonic() + 1, time.monotonic)[0] is None
        alternative = chess.Board("4q3/8/8/4k3/8/8/R7/7K w - - 0 1")
        assert not inspect_skewer(alternative, "h1g1", time.monotonic() + 1, time.monotonic)[0][
            "played"
        ]
        skewer_db.close()

        cache = {}
        for module in (protection_worker, protection_current):
            patch.setattr(module, "location", lambda *_: "in-memory")
            patch.setattr(module, "binding", lambda *_: "fixture")
            patch.setattr(module, "read", lambda *_args, **_kwargs: deepcopy(cache.get("state")))
        patch.setattr(
            protection_worker, "write", lambda _path, state: cache.update(state=deepcopy(state))
        )
        changes = games_db.connection.total_changes
        patch.setattr(scan, "TURN_LIMIT", 1)
        for expected in (1, 2, 3):
            protection_worker.run(games_db, "fixture_a", None)
            assert sum(len(game["results"]) for game in cache["state"]["games"]) == expected
        assert protection_worker.valid(cache["state"], "fixture")
        broken = deepcopy(cache["state"])
        broken["games"][0].pop("review")
        assert not protection_worker.valid(broken, "fixture")
        assert protection_current.current(games_db, "fixture_a", None)
        patch.setattr(protection_web, "database", lambda: games_db)
        protection_app = create_app(
            db_path=":memory:",
            subject="fixture_a",
            actor="operator",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        protection_client = protection_app.test_client()
        assert protection_client.get("/game-samples/protection").status_code == 403
        protection_client.environ_base["HTTP_TAILSCALE_USER_LOGIN"] = "fixture"
        protection_page = protection_client.get(
            "/game-samples/protection", base_url="https://coach.invalid"
        )
        assert protection_page.status_code == 200
        assert "dated protection view" in next(
            item["details"]
            for item in capability_report()["capabilities"]
            if item["id"] == "recurring_report"
        )
        assert (
            b"3 games" in protection_page.data and b"20 independent games" in protection_page.data
        )
        date = cache["state"]["games"][0]["date"]
        cache["state"]["games"][0]["date"] = "2000-01-01T00:00:00Z"
        assert protection_current.current(games_db, "fixture_a", None) is None
        cache["state"]["games"][0]["date"] = date
        assert games_db.connection.total_changes == changes
        games_db.connection.execute(
            "UPDATE pipeline_stages SET status='failed' WHERE game_id=1 AND stage='analysis'"
        )
        games_db.connection.commit()
        stale = protection_current.current(games_db, "fixture_a", None)
        assert next(game for game in stale["games"] if game["id"] == 1)["source_unavailable"]
        assert all(game["results"] for game in stale["games"] if game["id"] != 1)
        protection_page = protection_client.get(
            "/game-samples/protection", base_url="https://coach.invalid"
        )
        assert (
            b"Games with results withheld after a source change: 1 (1 previously scanned turns)"
            in protection_page.data
        )
        assert b"source, date, ownership record or review" in protection_page.data
        for _ in range(3):
            protection_worker.run(games_db, "fixture_a", None)
        assert not next(game for game in cache["state"]["games"] if game["id"] == 1)["results"]
        games_db.connection.execute(
            "UPDATE pipeline_stages SET status='complete' WHERE game_id=1 AND stage='analysis'"
        )
        games_db.connection.commit()
        for _ in range(3):
            protection_worker.run(games_db, "fixture_a", None)
        assert next(game for game in cache["state"]["games"] if game["id"] == 1)["results"]

        # A new frontier interrupted during selection retains only unconsumed games.
        ingest_pgn(games_db, pgn(3, "Qg1"))
        assert (
            run_analysis(
                games_db, 4, game_input(games_db, 4), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
        select = protection_worker.select

        def select_partial_protection(db, learner, games, state, deadline, **kwargs):
            ticks = iter((0, 0, float("inf")))
            with patch.context() as limited:
                limited.setattr(selection, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
                select(db, learner, games, state, deadline, **kwargs)

        patch.setattr(protection_worker, "select", select_partial_protection)
        protection_worker.run(games_db, "fixture_a", None)
        assert protection_worker.valid(cache["state"], "fixture")
        assert cache["state"]["retained"] and not cache["state"]["selection_complete"]
        patch.setattr(protection_worker, "select", select)
        protection_worker.run(games_db, "fixture_a", None)
        assert cache["state"]["selection_complete"]
        assert (
            sum(bool(game["results"]) for game in cache["state"]["games"] if game["id"] <= 3) == 3
        )
        # Exercise the independent report gates with two complete synthetic windows.
        sample_games = []
        for index in range(41):
            outcome = "missed" if (index < 3 or 20 <= index < 30) else "protected"
            if index == 19:
                outcome = "unknown"
            second = "opportunity_unresolved" if index == 0 else "no_opportunity"
            sample_games.append(
                {
                    "id": index + 1,
                    "date": f"2026-01-01T00:{59 - index:02}:00Z",
                    "eligible": 2,
                    "results": [[index * 2 + 1, outcome, None], [index * 2 + 2, second, None]],
                }
            )
        sample_state = {
            "games": sample_games,
            "selection_complete": True,
            "coverage": {
                "unknown_time_lower_bound": 0,
                "unknown_ownership_global_lower_bound": 0,
                "candidate_recheck_failed": 0,
                "game_limit_reached": False,
            },
            "duplicates": 0,
            "unavailable": 0,
            "time_control_reason": None,
        }
        with patch.context() as comparisons:
            from types import SimpleNamespace

            from chess_coach.dated_game_controls import reason as control_reason

            controls = sqlite3.connect(":memory:")
            controls.row_factory = sqlite3.Row
            controls.execute(
                "CREATE TABLE games(id INTEGER PRIMARY KEY, time_control TEXT, pgn TEXT)"
            )
            for index in range(41):
                value = "600+0" if index % 20 < 10 else "0+3"
                controls.execute(
                    "INSERT INTO games VALUES(?,?,?)",
                    (index + 1, value, f'[TimeControl "{value}"]\n\n*'),
                )

            def selected_controls():
                return [
                    (row, "white") for row in controls.execute("SELECT * FROM games ORDER BY id")
                ]

            assert control_reason(sample_games, selected_controls()) is None
            controls.execute("UPDATE games SET time_control=NULL WHERE id=41")
            assert control_reason(sample_games, selected_controls()) is None
            comparisons.setattr(protection_report, "current", lambda *_: sample_state)
            sample_result = protection_report.report(games_db, "fixture_a", None)
            assert sample_result["newer"]["unknown"] == 1
            assert sample_result["newer"]["opportunity_unresolved"] == 1
            assert sample_result["newer"]["no_opportunity"] == 19
            assert sample_result["newer"]["opportunities"] == 20
            assert sample_result["bounds"]["direction"] == "lower"
            protection_page = protection_client.get(
                "/game-samples/protection", base_url="https://coach.invalid"
            )
            assert b"/decisions/" in protection_page.data
            assert b"lower in the more recent sample" in protection_page.data
            for value, header, expected in (
                ("300+0", "300+0", "time_control_mismatch"),
                (None, None, "time_control_unknown"),
                ("600+0", "300+0", "time_control_source"),
            ):
                controls.execute(
                    "UPDATE games SET time_control=?, pgn=? WHERE id=1",
                    (value, f'[TimeControl "{header}"]\n\n*'),
                )
                sample_state["time_control_reason"] = control_reason(
                    sample_games, selected_controls()
                )
                assert sample_state["time_control_reason"] == expected
                blocked = protection_report.report(games_db, "fixture_a", None)
                assert blocked["bounds"]["status"] == "incomparable"
                assert blocked["newer"]["opportunities"] == sample_result["newer"]["opportunities"]
                page = protection_client.get(
                    "/game-samples/protection", base_url="https://coach.invalid"
                )
                assert b"A rate comparison is unavailable" in page.data
                assert b"Conservative missed-opportunity ranges" not in page.data
            controls.close()
            sample_state["time_control_reason"] = None
            for index in range(23, 30):
                sample_games[index]["results"] = [
                    [index * 2 + 1, "protected", None],
                    [index * 2 + 2, "no_opportunity", None],
                ]
            assert (
                protection_report.report(games_db, "fixture_a", None)["bounds"]["direction"]
                == "overlap"
            )
            sample_state["selection_complete"] = False
            assert (
                protection_report.report(games_db, "fixture_a", None)["bounds"]["status"]
                == "incomparable"
            )
        games_db.close()

    # A source-qualified created-exposure scan resumes without writing game data.
    from chess_coach import created_exposure_game_current as exposure_current
    from chess_coach import created_exposure_game_selection as exposure_selection
    from chess_coach import created_exposure_game_worker as exposure_worker
    from chess_coach.created_exposure_game_cache import valid as exposure_valid
    from chess_coach.created_exposure_game_proof import classify as exposure_classify
    from chess_coach.evidence_review import review_evidence
    from chess_coach.material_detector import process_decision
    from tests import test_material_pipeline as material_fixture

    with monkeypatch.context() as patch:
        import time

        import chess
        import chess.engine

        board = chess.Board("4k3/7p/8/2b5/P4q2/3R4/rP6/7K b - - 0 1")
        board.push_uci("h7h6")
        profile = {"mover": chess.ROOK, "target": chess.BISHOP, "geometry": (0, 1)}
        # Both independent windows advance, while the 41st game remains a boundary.
        seen = []
        patch.setattr(
            exposure_worker,
            "inspect",
            lambda _db, _learner, item, _deadline, _quota, **_kw: seen.append(item["id"]) or 1,
        )
        window = {
            "selection_complete": True,
            "profile": {},
            "games": [{"id": i, "results": [], "eligible": 1} for i in range(41)],
        }
        exposure_worker._scan(None, learner=None, state=window, deadline=time.monotonic() + 10)
        assert seen[:4] == [0, 20, 1, 21] and 40 not in seen
        patch.undo()

        from chess_coach import created_exposure_game_contrast as exposure_contrast
        from chess_coach import created_exposure_game_report as exposure_report
        from chess_coach.created_exposure_game_answer import follows
        from chess_coach.created_exposure_game_context import _same
        from chess_coach.created_exposure_game_counts import sample as exposure_sample

        assert follows("2024-01-02T00:00:00Z", "2024-01-01T00:00:00Z") is True
        assert follows("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z") is False
        assert follows(None, "2024-01-01T00:00:00Z") is None
        assert _same({("white", "rapid", "middlegame"): 2}, {("white", "rapid", "middlegame"): 1})
        assert not _same(
            {("white", "rapid", "middlegame"): 1}, {("black", "rapid", "middlegame"): 1}
        )
        sample = exposure_sample(
            [
                {
                    "id": 1,
                    "date": "2024-01-02",
                    "eligible": 1,
                    "results": [[1, "opportunity_unresolved", '["white","middlegame","deadline"]']],
                }
            ]
        )
        assert sample["examples"][0]["reason"] == "deadline"
        with patch.context() as isolated:
            isolated.setattr(
                exposure_contrast,
                "nominations",
                lambda *_: [
                    (chess.Move.from_uci("d3d4"), chess.Move.from_uci("c5d4")),
                    (chess.Move.from_uci("b2b3"), chess.Move.from_uci("a2b2")),
                ],
            )
            assert exposure_classify(
                board, "d3d4", profile, time.monotonic() + 1, time.monotonic
            ) == ("unknown", "ambiguous_target")
            isolated.setattr(
                exposure_report,
                "first_answer",
                lambda *_: {"attempt": "x", "answered_at": "2024-01-01T00:00:00Z"},
            )
            state = {
                "games": [{"id": 1, "date": "2024-01-02T00:00:00Z", "eligible": 0, "results": []}],
                "selection_complete": False,
                "profile": {},
                "coverage": {},
                "duplicates": 0,
                "unavailable": 0,
            }
            result = exposure_report._report(None, "learner", state, time.monotonic() + 1)
            assert result["comparable_reason"] == "selection_pending"
            assert result["relation"] == {"earlier": None, "newer": None}
            state["selection_complete"] = True
            state["coverage"] = {
                "unknown_time_lower_bound": 0,
                "unknown_ownership_global_lower_bound": 0,
                "candidate_recheck_failed": 0,
                "game_limit_reached": False,
            }
            result = exposure_report._report(None, "learner", state, time.monotonic() + 1)
            assert result["relation"] == {"earlier": None, "newer": None}

            from datetime import UTC, datetime, timedelta

            last = datetime(2024, 2, 10, tzinfo=UTC)
            state["games"] = [
                {
                    "id": i,
                    "date": (last - timedelta(days=i)).isoformat(),
                    "eligible": 0,
                    "results": [],
                }
                for i in range(41)
            ]
            isolated.setattr(exposure_report, "matched", lambda *_: True)
            result = exposure_report._report(None, "learner", state, time.monotonic() + 1)
            assert result["bounds"]["status"] == "sparse"
            assert result["relation"] == {"earlier": True, "newer": True}
            answer_date = state["games"][39]["date"]
            isolated.setattr(
                exposure_report,
                "first_answer",
                lambda *_: {"attempt": "x", "answered_at": answer_date},
            )
            result = exposure_report._report(None, "learner", state, time.monotonic() + 1)
            assert result["relation"] == {"earlier": False, "newer": True}
            answer_date = state["games"][19]["date"]
            result = exposure_report._report(None, "learner", state, time.monotonic() + 1)
            assert result["relation"] == {"earlier": False, "newer": False}

        for move, expected in (
            ("d3d4", "missed"),
            ("d3d5", "protected"),
            ("b2b3", "opportunity_unresolved"),
        ):
            assert (
                exposure_classify(board, move, profile, time.monotonic() + 1, time.monotonic)[0]
                == expected
            )
        assert (
            exposure_classify(board, "d3d4", profile, time.monotonic() - 1, time.monotonic)[0]
            == "unknown"
        )

        original_ingest = material_fixture.ingest_pgn

        def finished_ingest(db, text):
            return original_ingest(
                db, text.replace('[Result "*"]', '[Result "1-0"]').replace(" *", " 1-0")
            )

        patch.setattr(material_fixture, "ingest_pgn", finished_ingest)
        db = material_fixture.make_protection_game(":memory:", patch, created=True)
        learner = material_fixture.LEARNER
        evidence = process_decision(db, 1, learner)["evidence_ids"][0]
        original = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
        ingest_pgn(db, original.replace('[Event "?"]', '[Event "Cosmetic duplicate"]'))
        patch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: FakeEngine())
        for index in range(3):
            ingest_pgn(db, pgn(index, "Qg1").replace("fixture_a", learner))
            game_id = index + 3
            config = PipelineConfig(learner=learner, engine_path=sys.executable, nodes=100)
            assert (
                run_analysis(
                    db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
                )["status"]
                == "complete"
            )
        cache = {}
        for module in (exposure_selection, exposure_current):
            patch.setattr(module, "binding", lambda *_: "fixture-exposure")
            patch.setattr(module, "read", lambda *_args, **_kwargs: deepcopy(cache.get("state")))
        for module in (exposure_worker, exposure_current):
            patch.setattr(module, "location", lambda *_: "in-memory")
        patch.setattr(
            exposure_worker, "write", lambda _path, state: cache.update(state=deepcopy(state))
        )
        patch.setattr(scan, "TURN_LIMIT", 1)
        changes = db.connection.total_changes
        for expected in (1, 2, 3):
            exposure_worker.run(db, learner, None)
            assert sum(len(game["results"]) for game in cache["state"]["games"]) == expected
        state = cache["state"]
        assert exposure_valid(state, "fixture-exposure")
        assert state["profile"]["evidence_id"] == evidence and state["duplicates"] == 1
        assert all(game["id"] != state["profile"]["game_id"] for game in state["games"])
        assert exposure_current.current(db, learner, None) is not None
        assert db.connection.total_changes == changes

        patch.setattr(protection_web, "database", lambda: db)
        app = create_app(
            db_path=":memory:",
            subject=learner,
            actor="operator",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        client = app.test_client()
        assert (
            client.get(
                "/game-samples/created-exposure", base_url="https://coach.invalid"
            ).status_code
            == 403
        )
        page = client.get(
            "/game-samples/created-exposure",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert page.status_code == 200 and b"3 independent games" in page.data
        assert b"A comparison is unavailable" in page.data
        assert page.data.count(b"<h3>More recent games</h3>") == 1
        assert page.data.count(b"<h3>Earlier games</h3>") == 1
        review_evidence(db, evidence, decision="reject", actor="fixture")
        assert exposure_current.current(db, learner, None) is None
        db.close()

    # Exact linked material review and analysis changes invalidate their game.
    from chess_coach.evidence_review import review_evidence
    from chess_coach.material_detector import process_decision
    from chess_coach.protection_game_review import binding as protection_review
    from chess_coach.protection_game_source import binding as protection_analysis
    from tests.test_material_pipeline import LEARNER, make_protection_game

    with monkeypatch.context() as patch:
        material_db = make_protection_game(":memory:", patch, played="d4d5")
        evidence = process_decision(material_db, 1, LEARNER)["evidence_ids"][0]
        before, blocked = protection_review(material_db, 1, LEARNER)
        assert not blocked
        checked = {
            "id": 1,
            "analysis": protection_analysis(material_db, 1),
            "review": before,
            "results": [[1, "protected", None]],
        }
        assert protection_current._game(material_db, LEARNER, checked)
        review_evidence(material_db, evidence, decision="reject", actor="fixture")
        assert protection_review(material_db, 1, LEARNER)[1] == {1}
        assert not protection_current._game(material_db, LEARNER, checked)
        material_db.close()

    # A complete rotation visits every game and returns to the newest one.
    cursor = 0
    visited = []
    for _ in range(40):
        visited.append(cursor)
        cursor = scan._next(cursor, 40)
    assert len(set(visited)) == 40 and cursor == 0

    # An overall interruption leaves the turn for the next activation; a local
    # proof timeout becomes a terminal unknown so it cannot stall the scan.
    with monkeypatch.context() as patch:
        source = {
            "signature": "source",
            "pairs": [({"subject": True, "played_move": "a1a2", "position_id": 1}, None)],
        }
        patch.setattr(turns, "prepare", lambda *args: source)
        patch.setattr(turns, "recheck", lambda *args: None)
        patch.setattr(turns, "fingerprint", lambda value: value)
        patch.setattr(turns, "classify", lambda *args: ("unknown", "deadline"))
        item = {"id": 1, "signature": "source", "results": []}
        times = iter([0.0, 1.6])
        patch.setattr(turns, "time", SimpleNamespace(monotonic=lambda: next(times)))
        assert turns.inspect(None, "fixture_a", item, 2.0, 1) == 0
        assert not item["results"]
        times = iter([0.0, 0.0])
        assert turns.inspect(None, "fixture_a", item, 2.0, 1) == 1
        assert item["results"] == [[1, "unknown", "turn_deadline"]]

    root = tmp_path
    data = root / ".runtime" / "data"
    data.mkdir(parents=True)
    path = data / "games.sqlite"
    db = Database(path)
    db.initialize()

    def timed_game(index, move, **kwargs):
        return pgn(index, move, **kwargs).replace(
            '[Result "1-0"]', '[TimeControl "600+0"]\n[Result "1-0"]'
        )

    for index in range(41):
        ingest_pgn(db, timed_game(index, "Qg1" if index % 2 else "Qg7#"))
    ingest_pgn(db, timed_game(40, "Qg7#", event="Duplicate import"))
    before = db.connection.total_changes
    monkeypatch.setattr(scan, "TURN_LIMIT", 4)
    monkeypatch.setattr(turns, "classify", lambda *args: ("missed", None))
    scan.run(db, "fixture_a", root)
    partial = cached_report(db, "fixture_a", root)
    assert partial["comparable"] and partial["newer"]["checked"] == 2
    assert partial["newer"]["unchecked"] == 18
    assert partial["earlier"]["checked"] == 2 and not partial["qualified"]
    for _ in range(9):
        scan.run(db, "fixture_a", root)
    completed = cached_report(db, "fixture_a", root)
    assert completed["newer"]["missed"] == completed["earlier"]["missed"] == 20
    assert completed["newer"]["complete"] and completed["earlier"]["complete"]
    assert completed["duplicates"] == 1 and completed["qualified"]
    assert db.connection.total_changes == before
    assert location(db, root).stat().st_mode & 0o777 == 0o600

    # The fork scan uses its own bounded sidecar and dated cohorts.
    from chess_coach.fork_game_trend_report import report as fork_report
    from chess_coach.fork_game_trend_scan import run as run_forks

    with monkeypatch.context() as patch:
        patch.setattr(scan, "TURN_LIMIT", 40)
        run_forks(db, "fixture_a", root)
    fork_cohorts = fork_report(db, "fixture_a", root)
    assert fork_cohorts and fork_cohorts["selection_complete"]
    assert fork_cohorts["newer"]["games"] == fork_cohorts["earlier"]["games"] == 20
    assert fork_cohorts["newer"]["oldest"] > fork_cohorts["earlier"]["newest"]
    assert fork_cohorts["newer"]["opportunities"] == fork_cohorts["earlier"]["opportunities"] == 0
    assert fork_cohorts["newer"]["no_candidate"] == fork_cohorts["earlier"]["no_candidate"] == 20
    assert db.connection.total_changes == before

    # A separate capture scan resumes fairly without changing the mate cache.
    from chess_coach import capture_game_trend_paths as capture_paths
    from chess_coach import capture_game_trend_scan as capture_scan
    from chess_coach.capture_game_trend_paths import binding as capture_binding
    from chess_coach.capture_game_trend_paths import location as capture_location
    from chess_coach.capture_game_trend_report import report as capture_report
    from chess_coach.capture_game_trend_validate import validate as capture_validate

    mate_before = read(location(db, root), binding(db, "fixture_a"))
    # The new policy starts a distinct sidecar and keeps the earlier history.
    capture_cache = capture_location(db, root)
    assert capture_paths.PROOF_VERSION == "direct-capture-v3"
    assert capture_paths.VERSION == "capture-game-trend-v3"
    assert capture_cache.name.endswith(".capture-trend-v3.json")
    old_capture_cache = capture_cache.with_name(
        capture_cache.name.replace(".capture-trend-v3.json", ".capture-trend-v2.json")
    )
    old_capture_cache.write_bytes(b"synthetic prior capture cache")
    old_capture_cache.chmod(0o600)
    assert capture_report(db, "fixture_a", root) is None
    monkeypatch.setattr(
        capture_scan,
        "classify",
        lambda board, move, deadline, clock: ("played" if move.endswith("g7") else "other", None),
    )
    capture_scan.run(db, "fixture_a", root)
    assert old_capture_cache.read_bytes() == b"synthetic prior capture cache"
    capture_partial = capture_report(db, "fixture_a", root)
    assert capture_partial["comparable"] and not capture_partial["qualified"]
    assert capture_partial["bounds"]["status"] == "pending"
    assert capture_partial["newer"]["checked"] == capture_partial["earlier"]["checked"] == 2
    for _ in range(9):
        capture_scan.run(db, "fixture_a", root)
    capture_complete = capture_report(db, "fixture_a", root)
    assert capture_complete["qualified"] and capture_complete["duplicates"] == 1
    assert capture_complete["bounds"]["status"] == "available"
    assert capture_complete["bounds"]["direction"] == "overlap"
    assert capture_complete["bounds"]["earlier"] == {
        "lower": 10,
        "upper": 10,
        "total": 20,
        "unresolved": 0,
    }
    assert (
        capture_complete["newer"]["opportunities"]
        == capture_complete["earlier"]["opportunities"]
        == 20
    )
    assert capture_complete["newer"]["played"] == capture_complete["newer"]["other"] == 10
    # Cached counts remain visible when the stored control is missing or contradicts its PGN.
    for value, expected in ((None, "time_control_unknown"), ("300+0", "time_control_source")):
        db.connection.execute("UPDATE games SET time_control=? WHERE id=2", (value,))
        current_capture = capture_report(db, "fixture_a", root)
        assert current_capture["comparable_reason"] == expected
        assert (
            not current_capture["qualified"]
            and current_capture["bounds"]["status"] == "incomparable"
        )
        assert current_capture["newer"]["played"] == capture_complete["newer"]["played"]
    db.connection.execute("UPDATE games SET time_control='600+0' WHERE id=2")
    db.connection.commit()
    before = db.connection.total_changes
    assert capture_report(db, "fixture_a", root)["qualified"]
    assert read(location(db, root), binding(db, "fixture_a")) == mate_before
    assert old_capture_cache.read_bytes() == b"synthetic prior capture cache"
    capture_cache = capture_location(db, root)
    capture_state = read(
        capture_cache, capture_binding(db, "fixture_a"), validator=capture_validate
    )
    assert capture_state and capture_cache.stat().st_mode & 0o777 == 0o600

    # A newer arrival preserves the exact dated cohort through a partial refresh.
    from chess_coach.fork_game_trend_paths import location as fork_location
    from chess_coach.ingest import ingest_in_transaction

    caches = [location(db, root), capture_cache, fork_location(db, root)]
    originals = [cache.read_bytes() for cache in caches]
    reports = [cached_report, capture_report, fork_report]
    db.connection.execute("BEGIN IMMEDIATE")
    ingest_in_transaction(db, pgn(41, "Qg7#", event="Newer"))
    unchanged = db.connection.total_changes
    mutations = (
        lambda state: state["games"].reverse(),
        lambda state: state["games"][1].update(identity=state["games"][0]["identity"]),
    )
    for mutate in mutations:
        invalid = deepcopy(mate_before)
        mutate(invalid)
        write(caches[0], invalid)
        assert cached_report(db, "fixture_a", root) is None
    invalid = deepcopy(mate_before)
    invalid["games"][0]["results"][0][0] = 999999
    write(caches[0], invalid)
    assert cached_report(db, "fixture_a", root) is None
    caches[0].write_bytes(originals[0])
    historical_reports = [report_fn(db, "fixture_a", root) for report_fn in reports]
    for dated in historical_reports:
        assert dated and dated["historical"] and dated["through"] == completed["newer"]["newest"]
    assert fork_report(db, "fixture_a", root)["comparison"] is None
    assert db.connection.total_changes == unchanged
    scan.run(db, "fixture_a", root, seconds=0)
    capture_scan.run(db, "fixture_a", root, seconds=0)
    run_forks(db, "fixture_a", root, seconds=0)
    pending = [cache.read_bytes() for cache in caches]
    # The size cap discards optional history rather than blocking worker progress.
    from chess_coach import short_mate_trend_store as store

    pending_state = read(caches[0], binding(db, "fixture_a"))
    without_prior = {key: value for key, value in pending_state.items() if key != "prior"}
    write(caches[0], without_prior)
    with monkeypatch.context() as patch:
        patch.setattr(store, "MAX_BYTES", (len(pending[0]) + caches[0].stat().st_size) // 2)
        write(caches[0], pending_state)
        assert read(caches[0], binding(db, "fixture_a")) == without_prior
    caches[0].write_bytes(pending[0])
    for mutate in mutations:
        invalid = read(caches[0], binding(db, "fixture_a"))
        mutate(invalid["prior"])
        write(caches[0], invalid)
        assert cached_report(db, "fixture_a", root) is None
        caches[0].write_bytes(pending[0])
    for report_fn in reports:
        assert report_fn(db, "fixture_a", root)["historical"]
    assert [cache.read_bytes() for cache in caches] == pending
    assert db.connection.total_changes == unchanged

    db.connection.execute("SAVEPOINT insertion")
    ingest_in_transaction(db, pgn(25, "Qg7#", event="Inserted"))
    assert all(report_fn(db, "fixture_a", root) is None for report_fn in reports)
    db.connection.execute("ROLLBACK TO insertion")
    db.connection.execute("RELEASE insertion")
    db.connection.execute("SAVEPOINT changed")
    db.connection.execute(
        "UPDATE games SET result='0-1' WHERE id=?", (capture_state["games"][0]["id"],)
    )
    assert all(
        not (result := report_fn(db, "fixture_a", root)) or not result["historical"]
        for report_fn in reports
    )
    db.connection.execute("ROLLBACK TO changed")
    db.connection.execute("RELEASE changed")
    db.connection.execute("SAVEPOINT coverage")
    ingest_in_transaction(db, pgn(42, "Qg7#", event="Undated", dated=False))
    assert all(report_fn(db, "fixture_a", root) is None for report_fn in reports)
    db.connection.execute("ROLLBACK TO coverage")
    db.connection.execute("RELEASE coverage")
    scan.run(db, "fixture_a", root)
    capture_scan.run(db, "fixture_a", root)
    run_forks(db, "fixture_a", root)
    assert all(not report_fn(db, "fixture_a", root)["historical"] for report_fn in reports)
    assert "prior" not in read(caches[0], binding(db, "fixture_a"))
    db.connection.rollback()
    for cache, original in zip(caches, originals, strict=True):
        cache.write_bytes(original)
    before = db.connection.total_changes

    assert read(capture_cache, capture_binding(db, "fixture_a")) is None
    assert read(capture_cache, capture_binding(db, "fixture_b"), validator=capture_validate) is None
    retained = capture_state["games"][0]
    source = turns.prepare(db, "fixture_a", retained["id"])
    kept = _item(source, retained["signature"], {str(retained["id"]): retained})
    assert kept["results"] == retained["results"]
    wrong = deepcopy(retained)
    wrong["results"][0][0] = 999999
    rejected = _item(source, retained["signature"], {str(retained["id"]): wrong})
    assert not rejected["results"]

    # A checksum is not enough: cache records must remain tied to their sources.
    for mutate in (
        lambda state: state["games"][0].update(id=999999),
        lambda state: state["games"][0].update(signature="wrong"),
        lambda state: state["games"][1].update(identity=state["games"][0]["identity"]),
        lambda state: state["games"][1]["results"][0].__setitem__(
            0, state["games"][0]["results"][0][0]
        ),
        lambda state: state.update(duplicates=state["duplicates"] + 1),
    ):
        corrupted = deepcopy(capture_state)
        mutate(corrupted)
        write(capture_cache, corrupted)
        assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["date"] = "1900-01-01T00:00:00+00:00"
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["results"][0][0] = 999999
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["checked"].reverse()
    corrupted["games"].reverse()
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    capture_scan.run(db, "fixture_a", root)
    rebuilt = capture_report(db, "fixture_a", root)
    assert rebuilt and rebuilt["comparable"] and not rebuilt["qualified"]
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["eligible"] += 1
    corrupted["games"][0]["results"][0][0] = 999999
    corrupted["rotation"] = 0
    write(capture_cache, corrupted)
    capture_scan.run(db, "fixture_a", root)
    reset = read(capture_cache, capture_binding(db, "fixture_a"), validator=capture_validate)
    assert reset and not reset["checked"] and not reset["selection_complete"]
    write(capture_cache, capture_state)
    with monkeypatch.context() as patch:
        original_capture_binding = capture_binding(db, "fixture_a")
        patch.setattr(mate_paths, "PROOF_VERSION", "future-mate-policy")
        assert capture_binding(db, "fixture_a") == original_capture_binding
        assert binding(db, "fixture_a") != mate_before["binding"]
    with monkeypatch.context() as patch:
        patch.setattr(capture_paths, "PROOF_VERSION", "future-capture-policy")
        assert capture_report(db, "fixture_a", root) is None
    assert db.connection.total_changes == before

    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    client = app.test_client()
    for name, endpoint, dated in zip(
        ("trend_report", "capture_trend_report", "fork_trend_report"),
        ("/game-samples/short-mate", "/game-samples/captures", "/game-samples/knight-forks"),
        historical_reports,
        strict=True,
    ):
        with monkeypatch.context() as patch:
            patch.setattr(
                f"chess_coach.web_short_mate_game.{name}", lambda *_args, dated=dated: dated
            )
            page = client.get(
                endpoint,
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "fixture"},
            )
            assert (
                b"Historical sample through" in page.data
                and b"Newer games are pending" in page.data
            )
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.web_short_mate_game.capture_trend_report", lambda *_args: capture_partial
        )
        pending_page = client.get(
            "/game-samples/captures",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert b"pending turns to scan" in pending_page.data
        assert b"Conservative other-move rate ranges" not in pending_page.data
    for gate, explanation in (
        ("selection_pending", b"still selecting independent games"),
        ("source_unavailable", b"dates, ownership records or source checks could not be verified"),
        ("time_control_unknown", b"some game time controls are missing or unsupported"),
        ("time_control_source", b"a stored time control does not match"),
        ("time_control_mismatch", b"the two samples have different time-control distributions"),
        ("too_few_games", b"each sample needs 20 independent games"),
        ("between_tie", b"either side of the sample boundary share a start time"),
        ("frontier_tie", b"older sample and its boundary game share a start time"),
        ("frontier_limit", b"bounded search did not establish an older boundary game"),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(
                "chess_coach.web_short_mate_game.capture_trend_report",
                lambda *_args, _gate=gate: {
                    **capture_complete,
                    "qualified": False,
                    "comparable": False,
                    "comparable_reason": _gate,
                    "bounds": {"status": "incomparable"},
                },
            )
            incomparable_page = client.get(
                "/game-samples/captures",
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "fixture"},
            )
            assert explanation in incomparable_page.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_views.daily_plan", lambda *_args, **_kwargs: {})
        patch.setattr(
            "chess_coach.web_short_mate_game.capture_trend_report",
            lambda *_args: pytest.fail("Plan must not compute capture trend"),
        )
        plan = client.get(
            "/plan",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert plan.status_code == 200 and b"/game-samples/captures" in plan.data
    page = client.get(
        "/game-samples/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200 and b"20 missed" in page.data
    assert b"100.0% earlier and 100.0% more recent" in page.data
    assert b"fixture_a" not in page.data and b"/decisions/" in page.data
    fork_empty = client.get(
        "/game-samples/knight-forks",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert fork_empty.status_code == 200 and b"0 turns had a proved fork" in fork_empty.data
    assert b"Rates require" in fork_empty.data and b"0.0%" not in fork_empty.data
    assert client.get("/game-samples/captures", base_url="https://coach.invalid").status_code == 403
    capture_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert (
        capture_page.status_code == 200
        and b"50.0% earlier and 50.0% more recent" in capture_page.data
    )
    assert b"/decisions/" in capture_page.data and b"/plan/captures" in capture_page.data
    assert (
        b"fixture_a" not in capture_page.data and b"not necessarily a mistake" in capture_page.data
    )
    original = capture_state["games"][0]["results"][0]
    capture_state["games"][0]["results"][0] = [
        original[0],
        "opportunity_unresolved",
        "played_capture_unresolved",
    ]
    write(capture_cache, capture_state)
    unresolved_capture = capture_report(db, "fixture_a", root)
    assert not unresolved_capture["qualified"]
    assert unresolved_capture["newer"]["opportunity_games"] == 20
    capture_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert unresolved_capture["bounds"]["status"] == "available"
    assert unresolved_capture["bounds"]["direction"] == "overlap"
    assert unresolved_capture["newer"]["resolved_games"] == 19
    assert b"Conservative other-move rate ranges" in capture_page.data
    assert b"with unresolved opportunity status" in capture_page.data
    assert b"ranges overlap or touch" in capture_page.data
    capture_state["games"][0]["results"][0] = original
    original_newer = [item["results"][0][:] for item in capture_state["games"][:20]]
    for item in capture_state["games"][:16]:
        item["results"][0] = [item["results"][0][0], "no_opportunity", None]
    write(capture_cache, capture_state)
    sparse_capture = capture_report(db, "fixture_a", root)
    assert sparse_capture["newer"]["complete"] and sparse_capture["newer"]["opportunities"] == 4
    assert not sparse_capture["qualified"]
    assert sparse_capture["bounds"]["status"] == "sparse"
    sparse_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"at least five resolved capture opportunities" in sparse_page.data
    for item, old in zip(capture_state["games"][:20], original_newer, strict=True):
        item["results"][0] = old
    write(capture_cache, capture_state)

    # Unknown opportunity status and unresolved played choices both widen the bounds.
    scenario = deepcopy(capture_state)

    def set_capture_outcomes(items, values):
        for item, outcome in zip(items, values, strict=True):
            reason = {
                "unknown": "node_limit",
                "opportunity_unresolved": "played_capture_unresolved",
            }.get(outcome)
            item["results"][0] = [item["results"][0][0], outcome, reason]

    set_capture_outcomes(
        scenario["games"][:20], ["other"] * 17 + ["unknown"] * 2 + ["opportunity_unresolved"]
    )
    set_capture_outcomes(scenario["games"][20:40], ["other"] * 2 + ["played"] * 18)
    write(capture_cache, scenario)
    higher = capture_report(db, "fixture_a", root)
    assert higher["bounds"]["newer"] == {"lower": 17, "upper": 20, "total": 20, "unresolved": 3}
    assert higher["newer"]["unknown"] == 2 and higher["newer"]["opportunity_unresolved"] == 1
    assert higher["bounds"]["direction"] == "higher"
    higher_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert (
        b"17/20 to 20/20" in higher_page.data
        and b"higher in the more recent sample" in higher_page.data
    )
    set_capture_outcomes(
        scenario["games"][:20], ["played"] * 17 + ["unknown"] * 2 + ["opportunity_unresolved"]
    )
    set_capture_outcomes(scenario["games"][20:40], ["other"] * 20)
    write(capture_cache, scenario)
    lower = capture_report(db, "fixture_a", root)
    assert lower["bounds"]["direction"] == "lower"
    set_capture_outcomes(scenario["games"][:20], ["other"] * 3 + ["unknown"] * 2 + ["played"] * 15)
    set_capture_outcomes(scenario["games"][20:40], ["other"] * 5 + ["played"] * 15)
    write(capture_cache, scenario)
    touching = capture_report(db, "fixture_a", root)
    assert touching["bounds"]["newer"]["upper"] == touching["bounds"]["earlier"]["lower"]
    assert touching["bounds"]["direction"] == "overlap"

    # Five resolved turns from only two games do not meet the independence gate.
    from chess_coach.capture_game_trend_bounds import bounds as capture_bounds
    from chess_coach.capture_game_trend_report import _sample as capture_sample

    few_games = capture_sample(
        [
            {
                "date": "a",
                "eligible": 3,
                "results": [[101, "other", None], [102, "played", None], [103, "other", None]],
            },
            {"date": "b", "eligible": 2, "results": [[104, "played", None], [105, "other", None]]},
            {
                "date": "c",
                "eligible": 1,
                "results": [[106, "opportunity_unresolved", "played_capture_unresolved"]],
            },
        ]
    )
    assert few_games["opportunity_games"] == 3 and few_games["resolved_games"] == 2
    assert capture_bounds(True, few_games, capture_complete["earlier"])["status"] == "sparse"
    assert capture_bounds(False, few_games, capture_complete["earlier"])["status"] == "incomparable"
    # The explanatory gate is the same one used by other game trends.
    from chess_coach.mate_game_comparability import reason as cohort_reason
    from chess_coach.mate_game_trend import _comparable as cohort_comparable

    samples = [{"games": 20}, {"games": 20}]
    dates = [str(i) for i in range(41)]
    coverage = capture_complete["coverage"]
    assert cohort_reason(samples, dates, coverage, 0) is None
    assert cohort_comparable(samples, dates, coverage, 0)
    assert (
        cohort_reason(samples, dates, {**coverage, "unknown_time_lower_bound": 1}, 0)
        == "source_unavailable"
    )
    assert cohort_reason(samples, dates, coverage, 1) == "source_unavailable"
    assert cohort_reason([{"games": 19}, samples[1]], dates, coverage, 0) == "too_few_games"
    middle_tie = dates.copy()
    middle_tie[20] = middle_tie[19]
    assert cohort_reason(samples, middle_tie, coverage, 0) == "between_tie"
    end_tie = dates.copy()
    end_tie[40] = end_tie[39]
    assert cohort_reason(samples, end_tie, coverage, 0) == "frontier_tie"
    assert (
        cohort_reason(samples, dates[:40], {**coverage, "game_limit_reached": True}, 0)
        == "frontier_limit"
    )
    assert not cohort_comparable(samples, middle_tie, coverage, 0)
    earlier_ratio = {
        "played": 4,
        "other": 2,
        "unknown": 0,
        "opportunity_unresolved": 0,
        "unchecked": 0,
        "resolved_games": 3,
    }
    newer_ratio = {
        "played": 6,
        "other": 1,
        "unknown": 2,
        "opportunity_unresolved": 0,
        "unchecked": 0,
        "resolved_games": 3,
    }
    assert capture_bounds(True, earlier_ratio, newer_ratio)["direction"] == "overlap"
    newer_ratio = {**newer_ratio, "played": 6666, "other": 3334, "unknown": 0, "resolved_games": 20}
    assert round(100 * 2 / 6, 1) == round(100 * 3334 / 10000, 1)
    assert capture_bounds(True, earlier_ratio, newer_ratio)["direction"] == "higher"
    write(capture_cache, capture_state)
    cache = location(db, root)
    cached = read(cache, binding(db, "fixture_a"))
    old_result = cached["games"][0]["results"][0]
    cached["games"][0]["results"][0] = [old_result[0], "unknown", "node_limit"]
    write(cache, cached)
    unresolved = cached_report(db, "fixture_a", root)
    assert unresolved["newer"]["unknown"] == 1 and not unresolved["qualified"]
    page = client.get(
        "/game-samples/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"A rate comparison is unavailable" in page.data
    cached["games"][0]["results"][0] = old_result
    write(cache, cached)
    assert cached_report(db, "fixture_b", root) is None

    duplicate = db.connection.execute(
        "SELECT id FROM games WHERE event='Duplicate import'"
    ).fetchone()["id"]
    position = db.connection.execute(
        "SELECT fen,san,uci FROM positions WHERE game_id=? LIMIT 1", (duplicate,)
    ).fetchone()
    db.connection.executemany(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES (?,?,?,?,?)",
        [(duplicate, ply, *position) for ply in range(10000, 11000)],
    )
    db.connection.commit()
    assert source_signature(db, {"id": duplicate}) == "oversized"
    assert cached_report(db, "fixture_a", root) is None
    assert capture_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    oversized = cached_report(db, "fixture_a", root)
    assert oversized and not oversized["comparable"] and oversized["unavailable"] == 1
    db.connection.execute("DELETE FROM positions WHERE game_id=? AND ply>=10000", (duplicate,))
    db.connection.commit()
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    assert cached_report(db, "fixture_a", root)["comparable"]

    db.connection.execute("UPDATE games SET result='0-1' WHERE id=?", (duplicate,))
    db.connection.commit()
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    changed = cached_report(db, "fixture_a", root)
    assert changed and not changed["comparable"] and changed["unavailable"] == 1
    import json

    cache = location(db, root)
    corrupt = json.loads(cache.read_text())
    corrupt["games"] = [{}]
    cache.write_text(json.dumps(corrupt))
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    assert cached_report(db, "fixture_a", root) is not None
    cache.write_bytes(b"[" * 1500 + b"]" * 1500)
    assert cached_report(db, "fixture_a", root) is None
    cache.write_text("{invalid")
    assert cached_report(db, "fixture_a", root) is None
    db.close()

    # Real worker-to-browser readiness: proved played, proved alternative,
    # and a geometric fork whose bounded proof cannot qualify it.
    import time

    import chess
    import chess.engine

    from chess_coach import fork_game_proof, fork_game_trend_paths
    from chess_coach.fork_targets import targets

    # An immediate legal capture refutes the same-knight fork, but a pinned
    # attacker does not. The latter still requires the original universal proof.
    refuted = "3k4/3bq3/8/8/1N6/8/8/7K w - - 0 1"
    pinned = "3k4/3bq3/8/8/1N6/8/8/3R3K w - - 0 1"
    for fen, expected in ((refuted, "d7c6"), (pinned, None)):
        board = chess.Board(fen)
        move = board.parse_uci("b4c6")
        after, _ = targets(board, move)
        capture = chess.Move.from_uci("d7c6")
        assert capture in after.pseudo_legal_moves
        assert (capture in after.legal_moves) == bool(expected)
        assert fork_game_proof._capture_refutation(after, move.to_square) == expected
        outcome, reason = fork_game_proof.classify(
            board, move.uci(), time.monotonic() + 5, time.monotonic
        )
        assert (outcome, reason) == (
            ("no_candidate", None) if expected else ("unresolved", "unresolved_roots")
        )
    assert fork_game_trend_paths.PROOF_VERSION == "knight-fork-game-v2"

    fork_path = data / "fork-games.sqlite"
    fork_db = Database(fork_path)
    fork_db.initialize()
    supported = "b3k3/4B3/5K1p/1N3b2/8/8/8/8 w - - 0 2"
    unproved = "b3k3/4B3/5K1p/1N3b2/8/8/8/r7 w - - 0 2"
    for index, (fen, move) in enumerate(
        ((supported, "Nc7+"), (supported, "Kg7"), (unproved, "Kg7"), (refuted, "Kg1")), 1
    ):
        ingest_pgn(fork_db, pgn(index, move).replace(FEN, fen))
    changes = fork_db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(scan, "TURN_LIMIT", 1)
        run_forks(fork_db, "fixture_a", root)
        pending = fork_report(fork_db, "fixture_a", root)
        assert pending and pending["newer"]["scanned"] == 1
        assert pending["newer"]["unchecked"] == 3
        assert pending["newer"]["opportunities"] == 0 and pending["newer"]["no_candidate"] == 1
        for _ in range(3):
            run_forks(fork_db, "fixture_a", root)
    fork_result = fork_report(fork_db, "fixture_a", root)
    assert fork_result and fork_result["selection_complete"]
    newer, earlier = fork_result["newer"], fork_result["earlier"]
    assert (newer["games"], newer["eligible"], newer["scanned"]) == (4, 4, 4)
    assert (newer["opportunities"], newer["played"], newer["awaiting"]) == (2, 1, 1)
    assert newer["no_candidate"] == 1
    assert newer["unresolved"] == newer["unresolved_roots"] == 1
    assert earlier["games"] == 0 and newer["unchecked"] == 0
    assert newer["examples"][0]["outcome"] in {"played", "awaiting"}
    assert fork_game_trend_paths.location(fork_db, root).stat().st_mode & 0o777 == 0o600
    assert fork_db.connection.total_changes == changes

    fork_app = create_app(
        db_path=fork_path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    fork_client = fork_app.test_client()
    fork_headers = {"Tailscale-User-Login": "fixture"}
    fork_url = "/game-samples/knight-forks"
    assert fork_client.get(fork_url, base_url="https://coach.invalid").status_code == 403
    version = fork_db.connection.execute("PRAGMA data_version").fetchone()[0]
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_game_proof, "fork_proof", lambda *_args, **_kwargs: pytest.fail("browser proof")
        )
        patch.setattr(
            chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: pytest.fail("engine")
        )
        page = fork_client.get(fork_url, base_url="https://coach.invalid", headers=fork_headers)
        plan = fork_client.get("/plan", base_url="https://coach.invalid", headers=fork_headers)
    assert page.status_code == 200 and b"4 of 4 learner turns attempted" in page.data
    assert (
        b"1 had no qualifying fork candidate within this scope after legal refutations" in page.data
    )
    assert b"2 turns had a proved fork" in page.data and b"1 await comparison" in page.data
    assert b"1 turns had at least one unproved" in page.data
    assert b"/decisions/" in page.data and b"Rates require" in page.data
    assert b"fixture_a" not in page.data and b"fixture_b" not in page.data
    assert b"/game-samples/knight-forks" in plan.data
    assert fork_db.connection.execute("PRAGMA data_version").fetchone()[0] == version
    assert fork_db.connection.total_changes == changes

    from chess_coach.fork_game_trend_validate import validate as fork_validate

    fork_cache = fork_game_trend_paths.location(fork_db, root)
    fork_binding = fork_game_trend_paths.binding(fork_db, "fixture_a")
    fork_state = read(fork_cache, fork_binding, validator=fork_validate)
    assert fork_state and read(fork_cache, fork_binding) is None
    malformed = deepcopy(fork_state)
    unresolved = next(
        row for game in malformed["games"] for row in game["results"] if row[1] == "unresolved"
    )
    unresolved[2] = None
    write(fork_cache, malformed)
    assert fork_report(fork_db, "fixture_a", root) is None
    write(fork_cache, fork_state)

    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "PROOF_VERSION", "changed-proof")
        assert fork_report(fork_db, "fixture_a", root) is None
    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "VALUES", {1: 2})
        assert fork_report(fork_db, "fixture_a", root) is None

    # Exercise the real classifier deadline through the shared worker and sidecar.
    from chess_coach import fork_game_trend_scan

    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "PROOF_VERSION", "deadline-fixture")
        patch.setattr(scan, "TURN_LIMIT", 1)
        patch.setattr(
            fork_game_trend_scan,
            "classify",
            lambda board, played, deadline, clock: fork_game_proof.classify(
                board, played, deadline, lambda: deadline
            ),
        )
        run_forks(fork_db, "fixture_a", root)
        deadline_state = read(
            fork_cache, fork_game_trend_paths.binding(fork_db, "fixture_a"), validator=fork_validate
        )
        assert deadline_state
        assert [row[1:] for game in deadline_state["games"] for row in game["results"]] == [
            ["unknown", "turn_deadline"]
        ]
    write(fork_cache, fork_state)
    fork_db.connection.execute("UPDATE games SET result='0-1' WHERE id=1")
    fork_db.connection.commit()
    assert fork_report(fork_db, "fixture_a", root) is None
    stale = fork_client.get(fork_url, base_url="https://coach.invalid", headers=fork_headers)
    assert b"scan is pending or its sources changed" in stale.data
    fork_db.close()

    # A full, independent synthetic sample with current same-source analysis.
    import sys

    from chess_coach import fork_miss_candidate, fork_miss_worker
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_fork_pipeline import Engine

    matched_path = data / "matched-forks.sqlite"
    matched = Database(matched_path)
    matched.initialize()
    fen = "r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1"
    for index in range(41):
        position = fen if index != 1 else "r3k3/7p/8/1N6/8/8/6P1/r6K w - - 0 1"
        move = "Kh2" if index == 1 else ("Kg1" if index % 2 else "Nc7+")
        game = pgn(index, move).replace(FEN, position)
        ingest_pgn(matched, game.replace('[Result "1-0"]', '[TimeControl "600+0"]\n[Result "1-0"]'))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_a", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    engine_hash = engine_identity(sys.executable)
    for game_id in (1, *range(4, 42)):
        assert (
            run_analysis(matched, game_id, game_input(matched, game_id), config, engine_hash)[
                "status"
            ]
            == "complete"
        )
    for _ in range(30):
        run_forks(matched, "fixture_a", root)
        current = fork_report(matched, "fixture_a", root)
        if current and current["newer"]["unchecked"] == current["earlier"]["unchecked"] == 0:
            break
    else:
        pytest.fail("readiness scan did not finish")
    for _ in range(15):
        fork_miss_worker.run(matched, "fixture_a", root)
        current = fork_report(matched, "fixture_a", root)
        if (
            current
            and current["comparison"]
            and not (
                current["comparison"]["newer"]["pending"]
                + current["comparison"]["earlier"]["pending"]
            )
        ):
            break
    assert current["comparison"] and not current["comparison"]["qualified"]
    assert current["comparison"]["earlier"]["unresolved"] == 1
    assert (
        run_analysis(matched, 3, game_input(matched, 3), config, engine_hash)["status"]
        == "complete"
    )
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    fork_miss_worker.run(matched, "fixture_a", root)
    current = fork_report(matched, "fixture_a", root)
    assert current["comparison"]["qualified"]
    assert current["comparison"]["newer"]["miss"] == 10
    assert current["comparison"]["earlier"]["miss"] == 9
    assert current["newer"]["unknown"] == 0 and current["earlier"]["unknown"] == 1
    assert (
        current["comparison"]["newer"]["played"] == current["comparison"]["earlier"]["played"] == 10
    )
    app = create_app(
        db_path=matched_path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_miss_candidate, "fork_proof", lambda *_args, **_kw: pytest.fail("browser proof")
        )
        patch.setattr(
            chess.engine.SimpleEngine, "popen_uci", lambda *_args: pytest.fail("browser engine")
        )
        page = app.test_client().get(
            "/game-samples/knight-forks",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
    assert b"50.0% across 20 resolved opportunities" in page.data
    assert b"47.4% across 19 resolved opportunities" in page.data

    # A different known time control blocks comparison even for an unsupported turn.
    from chess_coach.fork_miss_time import _times

    matched.connection.execute("UPDATE games SET time_control='0+3' WHERE id=2")
    matched.connection.commit()
    assert _times(matched, [{"id": 2}])["0+3"] == 1
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    matched.connection.execute("UPDATE games SET time_control='0+0' WHERE id=2")
    assert _times(matched, [{"id": 2}]) is None
    matched.connection.execute("UPDATE games SET time_control='600+0' WHERE id=2")
    matched.connection.commit()

    # A proof timeout remains pending, then the worker resumes that exact turn.
    from chess_coach.fork_game_proof import Deadline
    from chess_coach.fork_miss_store import binding as miss_binding
    from chess_coach.fork_miss_store import location as miss_location
    from chess_coach.fork_miss_store import validate as miss_validate

    miss_cache = miss_location(matched, root)
    miss_key = miss_binding(matched, "fixture_a")
    miss_state = read(miss_cache, miss_key, validator=miss_validate)
    position = next(key for key, row in miss_state["rows"].items() if row[2] == "miss")
    miss_state["rows"][position][2] = "retry"
    write(miss_cache, miss_state)
    with monkeypatch.context() as patch:

        def expire(*args, **kwargs):
            raise Deadline()

        patch.setattr(fork_miss_candidate, "fork_proof", expire)
        fork_miss_worker.run(matched, "fixture_a", root)
    timed = fork_report(matched, "fixture_a", root)["comparison"]
    assert not timed["qualified"] and timed["newer"]["pending"] + timed["earlier"]["pending"] == 1
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Late per-entry expiry retries, and a cycle timeout preserves prior entries.
    import sqlite3
    import time
    from contextlib import contextmanager

    from chess_coach import fork_miss_entry, fork_miss_progress
    from chess_coach.opening_queue_budget import BrowserBudget
    from chess_coach.tactical_course_budget import PreviewUnavailable

    late = {"expired": False}
    original_config = fork_miss_entry.configuration
    original_check = fork_miss_entry._check

    def late_config(*args):
        result = original_config(*args)
        late["expired"] = True
        return result

    def late_check(deadline):
        if late["expired"]:
            raise Deadline()
        original_check(deadline)

    with monkeypatch.context() as patch:
        patch.setattr(fork_miss_entry, "configuration", late_config)
        patch.setattr(fork_miss_entry, "_check", late_check)
        retry = fork_miss_entry._entry(
            matched,
            "fixture_a",
            miss_state["rows"][position][0],
            int(position),
            "awaiting",
            time.monotonic() + 10,
        )
        assert retry[2] == "retry"

    readiness_cache = fork_game_trend_paths.location(matched, root)
    readiness_key = fork_game_trend_paths.binding(matched, "fixture_a")
    full = read(readiness_cache, readiness_key, validator=fork_validate)
    entries = fork_miss_progress._entries(full)
    first, second = (str(entry[1]) for entry in entries[:2])
    paused = read(miss_cache, miss_key, validator=miss_validate)
    first_result = paused["rows"][first][2]
    paused["rows"][first][2] = paused["rows"][second][2] = "retry"
    paused["rotation"] = 0
    write(miss_cache, paused)
    original_step = fork_miss_progress._step
    steps = []

    original_scope = BrowserBudget.scope

    @contextmanager
    def stop_second(self, *, snapshot):
        with original_scope(self, snapshot=snapshot):
            yield
            steps.append(1)
            if len(steps) == 2:
                raise PreviewUnavailable("synthetic timeout after guarded work")

    with monkeypatch.context() as patch:
        patch.setattr(BrowserBudget, "scope", stop_second)
        fork_miss_worker.run(matched, "fixture_a", root)
    resumed = read(miss_cache, miss_key, validator=miss_validate)
    assert resumed["rows"][first][2] == first_result and resumed["rows"][second][2] == "retry"
    assert resumed["rotation"] == 2
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Do not publish the completed prefix if another connection changes the data.
    write(miss_cache, paused)
    steps.clear()
    other = sqlite3.connect(matched_path)

    def change_second(*args):
        steps.append(1)
        if len(steps) == 2:
            other.execute("UPDATE analysis_runs SET engine_version='temporary' WHERE game_id=3")
            other.commit()
            raise PreviewUnavailable("synthetic source change")
        return original_step(*args)

    with monkeypatch.context() as patch:
        patch.setattr(fork_miss_progress, "_step", change_second)
        fork_miss_worker.run(matched, "fixture_a", root)
    assert read(miss_cache, miss_key, validator=miss_validate) == paused
    other.execute("UPDATE analysis_runs SET engine_version='synthetic' WHERE game_id=3")
    other.commit()
    other.close()
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Retain exact earlier opportunities when the readiness prefix grows.
    readiness_cache = fork_game_trend_paths.location(matched, root)
    readiness_key = fork_game_trend_paths.binding(matched, "fixture_a")
    full = read(readiness_cache, readiness_key, validator=fork_validate)
    partial = deepcopy(full)
    game = next(game for game in partial["games"] if game["results"][0][1] == "awaiting")
    game["results"].pop()
    write(readiness_cache, partial)
    fork_miss_worker.run(matched, "fixture_a", root)
    retained = read(miss_cache, miss_key, validator=miss_validate)["rows"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    grown = read(miss_cache, miss_key, validator=miss_validate)["rows"]
    assert all(grown[key] == row for key, row in retained.items())
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Unproved turns can change the order, so overlapping bounds withhold rates.
    uncertain_state = deepcopy(full)
    unknown = next(
        row
        for game in uncertain_state["games"]
        for row in game["results"]
        if row[1:] == ["unknown", "unsupported_position"]
    )
    unknown[1:] = ["unresolved", "unresolved_roots"]
    write(readiness_cache, uncertain_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    uncertain = fork_report(matched, "fixture_a", root)["comparison"]
    assert uncertain["earlier"]["uncertain"] == 1 and not uncertain["qualified"]
    hidden = app.test_client().get(
        "/game-samples/knight-forks",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"additional turns had unproved fork candidates" in hidden.data
    assert b"verified miss rate was" not in hidden.data
    from chess_coach.fork_miss_bounds import separated

    assert separated(
        [
            {"opportunities": 5, "miss": 0, "uncertain": 1},
            {"opportunities": 10, "miss": 10, "uncertain": 0},
        ]
    )

    # Other unproved roots on an already proved turn are not extra opportunities.
    proved_state = deepcopy(full)
    played = next(
        row for game in proved_state["games"] for row in game["results"] if row[1] == "played"
    )
    played[2] = "unresolved_roots"
    write(readiness_cache, proved_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    proved = fork_report(matched, "fixture_a", root)["comparison"]
    assert proved["newer"]["uncertain"] == proved["earlier"]["uncertain"] == 0
    assert proved["qualified"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A readiness proof timeout blocks rates, unlike known unsupported coverage.
    timeout_state = deepcopy(full)
    unknown = next(
        row
        for game in timeout_state["games"]
        for row in game["results"]
        if row[1:] == ["unknown", "unsupported_position"]
    )
    unknown[2] = "turn_deadline"
    write(readiness_cache, timeout_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A valid checksum cannot turn an awaiting result into a played result.
    stable = read(miss_cache, miss_key, validator=miss_validate)
    forged = deepcopy(stable)
    miss_position = next(key for key, row in forged["rows"].items() if row[2] == "miss")
    forged["rows"][miss_position][2] = "played"
    write(miss_cache, forged)
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    write(miss_cache, stable)

    # Changed engine identity invalidates the source and blocks matched analysis.
    matched.connection.execute(
        "UPDATE analysis_runs SET engine_version='different synthetic engine' WHERE game_id=3"
    )
    matched.connection.commit()
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    fork_miss_worker.run(matched, "fixture_a", root)
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    matched.connection.execute(
        "UPDATE analysis_runs SET engine_version='synthetic' WHERE game_id=3"
    )
    matched.connection.commit()
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A geometric played knight root may be an unresolved equivalent.
    board = chess.Board(fen)
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_miss_candidate, "fork_proof", lambda *_args, **_kw: pytest.fail("unexpected proof")
        )
        assert (
            fork_miss_candidate.candidate(
                board, chess.Move.from_uci("b5c7"), chess.Move.from_uci("b5d6"), {}, lambda: None
            )
            == "unresolved"
        )

    matched.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=3 AND role='best'"
    )
    matched.connection.commit()
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    matched.close()
