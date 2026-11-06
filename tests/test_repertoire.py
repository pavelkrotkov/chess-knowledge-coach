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
    data_dir = tmp_path / ".runtime" / "data"
    data_dir.mkdir(parents=True, mode=0o700)
    planning_dir = tmp_path / ".runtime" / "planning"
    planning_dir.mkdir(mode=0o700)
    path = data_dir / "test.sqlite"
    db = Database(path)
    db.initialize()
    for text in (
        game("Learner", "Opponent", "1. d4 d5 2. Nf3 Nf6 3. c4", second=3),
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5 3. g3", "0-1", second=3),
        game("Opponent", "Learner", "1. d4 d5 2. Nf3 Nf6", second=2),
        game("Other", "Opponent", "1. d4 d5 2. Nf3 Nf6", second=6),
        game("Learner", "Opponent", "1. e4 e5", "*", second=1),
        game("Learner", "Opponent", "1. c4 e5"),
        game("Learner", "Opponent", "1. Nf3 d5", second=70),
    ):
        ingest_pgn(db, text)
    source = tmp_path / "opening.tsv"
    source.write_text(
        "eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\nA04\tAlternate\tNf3 Nf6 d4 d5\nD20\tOther\td4 Nf6 c4\nD30\tC line\td4 d5 Nf3 Nf6 c4\nA10\tG line\tNf3 Nf6 d4 d5 g3\n"
    )
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
    from chess_coach.opening_decision import inspect as inspect_opening

    monkeypatch.setattr("chess_coach.opening_decision_budget.VERSION", "test")
    monkeypatch.setattr("chess_coach.opening_decision_budget.SOURCE", "cc0://test")
    from chess_coach.classification_inputs import opening_graph, opening_input, position_input
    from chess_coach.fact_fingerprint import canonical, digest

    dataset_id = db.connection.execute(
        "SELECT id FROM opening_datasets WHERE version=?", ("test",)
    ).fetchone()[0]
    graph = opening_graph(db, dataset_id)
    monkeypatch.setattr(
        "chess_coach.opening_decision_budget.GRAPH_SHA256", digest(canonical(graph))
    )
    old_payload = {
        "positions": position_input(db, 1),
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }
    assert opening_input(db, 1, dataset_id) == digest(canonical(old_payload))
    assert opening_input(db, 1, dataset_id, graph=graph) == digest(canonical(old_payload))
    first_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=1"
    ).fetchone()[0]
    transposed_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    black_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=3 AND ply=2"
    ).fetchone()[0]
    first = inspect_opening(db, 1, first_move, "learner")
    transposed = inspect_opening(db, 2, transposed_move, "learner")
    black_choice = inspect_opening(db, 3, black_move, "learner")
    assert first["played"] == "d4" and transposed["played"] == "Nf3"
    assert first["catalog"]["parent"] == transposed["catalog"]["parent"]
    from chess_coach.opening_decision_source import source as opening_source

    after_first = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=5"
    ).fetchone()[0]
    after_second = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=5"
    ).fetchone()[0]
    branch_first = inspect_opening(db, 1, after_first, "learner")
    branch_second = inspect_opening(db, 2, after_second, "learner")
    assert branch_first["catalog"]["parent"] == branch_second["catalog"]["parent"]
    assert "g3" in [item["san"] for item in branch_first["catalog"]["items"]]
    assert "c4" in [item["san"] for item in branch_second["catalog"]["items"]]
    board_first = opening_source(db, 1, after_first, "learner")[2]
    board_second = opening_source(db, 2, after_second, "learner")[2]
    assert len(board_first.move_stack) == len(board_second.move_stack) == 4
    assert board_first.move_stack != board_second.move_stack
    assert "Nf3" in [item["san"] for item in first["catalog"]["items"]]
    assert "d4" in [item["san"] for item in transposed["catalog"]["items"]]
    assert black_choice["color"] == "black" and black_choice["played"] == "d5"
    assert "Nf6" in [item["san"] for item in black_choice["catalog"]["items"]]
    assert first["analysis"]["status"] == "current analysis unavailable"

    # A catalog selection is measured once, with no scout or global-best claim.
    import json
    from types import SimpleNamespace

    import chess
    import chess.engine

    import chess_coach.opening_measure_engine as opening_engine
    import chess_coach.opening_measure_grade as opening_grade
    import chess_coach.opening_measure_prepare as opening_measure
    import chess_coach.opening_measure_search as opening_search
    import chess_coach.ops_opening_measure as opening_cli

    db.connection.commit()
    monkeypatch.setenv("CHESS_SUBJECT", "learner")
    engine_calls = []

    class Engine:
        def analyse(self, board, limit, *, multipv, root_moves):
            engine_calls.append((multipv, [move.uci() for move in root_moves]))
            return [
                {
                    "pv": [root_moves[0]],
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "depth": 12,
                    "nodes": 100000,
                },
                {
                    "pv": [root_moves[1]],
                    "score": chess.engine.PovScore(chess.engine.Cp(120), board.turn),
                    "depth": 12,
                    "nodes": 100000,
                },
            ]

    monkeypatch.setattr(
        opening_measure, "_config", lambda *args: ("engine", {"engine_path": "engine"})
    )
    monkeypatch.setattr(
        opening_engine, "start_engine", lambda *args, **kwargs: (Engine(), SimpleNamespace(id={}))
    )
    monkeypatch.setattr(opening_engine, "stop_engine", lambda engine: True)
    destination = tmp_path / "opening-result.json"
    monkeypatch.setattr(opening_cli, "planning", lambda *args: None)
    monkeypatch.setattr(opening_cli, "paths", lambda *args: (path, destination))
    opening_cli.prepare(tmp_path, 1, first_move, "g1f3", destination, "engine")
    saved = json.loads(destination.read_text())
    assert saved["sha256"] == digest(canonical(saved["measurement"]))
    result = saved["measurement"]["result"]
    assert result["status"] == "complete"
    assert abs(result["lines"][0]["score_value"] - result["lines"][1]["score_value"]) == 120
    assert engine_calls == [(2, ["d2d4", "g1f3"])]
    assert destination.stat().st_mode & 0o777 == 0o400
    with pytest.raises(ValueError):
        opening_measure._prepare(db, 1, first_move, "e2e4", tmp_path / "bad.json", "engine")
    assert len(engine_calls) == 1

    # Reject non-exact or unequal-depth output, and never publish stale results.
    raw = Engine().analyse(
        chess.Board(),
        None,
        multipv=2,
        root_moves=[chess.Move.from_uci("d2d4"), chess.Move.from_uci("g1f3")],
    )
    raw[1]["depth"] = 11
    assert (
        opening_grade.grade(
            chess.Board(), {"id": first_move, "uci": "d2d4"}, ["d2d4", "g1f3"], raw, None
        )[0]
        is None
    )
    raw[1]["depth"] = 12
    raw[1]["lowerbound"] = True
    assert (
        opening_grade.grade(
            chess.Board(), {"id": first_move, "uci": "d2d4"}, ["d2d4", "g1f3"], raw, None
        )[0]
        is None
    )

    raw[1].pop("lowerbound")
    raw[1]["score"] = chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE)
    assert (
        opening_grade.grade(
            chess.Board(), {"id": first_move, "uci": "d2d4"}, ["d2d4", "g1f3"], raw, None
        )[0]
        is None
    )

    class OversizedEngine:
        timeout = 1

        def analyse(self, *args, **kwargs):
            raw[0]["nodes"] = 200001
            return raw

    import time

    excessive = opening_search.search(
        OversizedEngine(),
        chess.Board(),
        {"id": first_move, "uci": "d2d4"},
        "g1f3",
        time.monotonic() + 10,
    )
    assert excessive["status"] == "insufficient"
    assert excessive["reason"] == "node_limit_unverified"

    class TimedOutEngine:
        timeout = 1

        def analyse(self, *args, **kwargs):
            raise TimeoutError

    timed_out = opening_search.search(
        TimedOutEngine(),
        chess.Board(),
        {"id": first_move, "uci": "d2d4"},
        "g1f3",
        time.monotonic() + 10,
    )
    assert timed_out == {"status": "insufficient", "reason": "engine_timeout"}

    def failed_start(*args, **kwargs):
        raise RuntimeError("sanitized")

    with monkeypatch.context() as patch:
        patch.setattr(opening_engine, "start_engine", failed_start)
        failed = opening_engine.measure(
            "engine",
            {},
            chess.Board(),
            {"id": first_move, "uci": "d2d4"},
            "g1f3",
            time.monotonic() + 10,
        )
    assert failed == {"status": "insufficient", "reason": "engine_start_failed"}

    import sqlite3

    real_measure = opening_measure.measure

    def concurrent_measure(*args):
        measured = real_measure(*args)
        other = sqlite3.connect(path)
        other.execute("CREATE TABLE test_concurrent_marker (id INTEGER)")
        other.commit()
        other.close()
        return measured

    monkeypatch.setattr(opening_measure, "measure", concurrent_measure)
    stale = tmp_path / "stale-result.json"
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with pytest.raises(PreviewUnavailable):
        opening_measure._prepare(db, 1, first_move, "g1f3", stale, "engine")
    assert not stale.exists()
    monkeypatch.setattr(opening_measure, "measure", real_measure)

    with pytest.raises(ValueError, match="unavailable"):
        inspect_opening(db, 3, first_move, "learner")
    with pytest.raises(ValueError, match="unavailable"):
        inspect_opening(db, 1, first_move, "other")
    db.connection.execute("UPDATE opening_datasets SET content_revision=2 WHERE version='test'")
    with pytest.raises(ValueError, match="pinned"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.execute("UPDATE opening_datasets SET content_revision=1 WHERE version='test'")
    db.connection.commit()
    # The bounded graph and fingerprint share a short snapshot, not the game replay.
    import chess_coach.opening_decision_budget as opening_budget
    import chess_coach.opening_decision_source as opening_source_module

    graph_reader = opening_budget.opening_graph
    history_reader = opening_source_module._history

    def checked_graph(database, selected_dataset):
        assert database.connection.in_transaction
        return graph_reader(database, selected_dataset)

    def checked_history(database, *args):
        assert not database.connection.in_transaction
        return history_reader(database, *args)

    with monkeypatch.context() as patch:
        patch.setattr(opening_budget, "opening_graph", checked_graph)
        patch.setattr(opening_source_module, "_history", checked_history)
        assert inspect_opening(db, 1, first_move, "learner")["played"] == "d4"

    original_fen = db.connection.execute(
        "SELECT fen FROM positions WHERE id=?", (first_move,)
    ).fetchone()[0]
    db.connection.execute("UPDATE positions SET fen=? WHERE id=?", (original_fen + " ", first_move))
    with pytest.raises(ValueError, match="stale"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.rollback()
    import chess

    from chess_coach.opening_decision_catalog import catalog

    dataset_id = first["opening"]["dataset_id"]
    db.connection.execute(
        "INSERT INTO opening_edges(dataset_id,parent_key,child_key,uci) VALUES(?,?,?,?)",
        (dataset_id, first["catalog"]["parent"], "invalid-child", "a1a8"),
    )
    filtered = catalog(db, dataset_id, chess.Board(), "d2d4")
    assert "a1a8" not in [item["uci"] for item in filtered["items"]]
    from chess_coach.opening_classification import classify_game

    classify_game(db, 1, version="test", source_url="cc0://test")
    with pytest.raises(ValueError, match="pinned opening graph differs"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.rollback()
    with pytest.raises(ValueError, match="unavailable"):
        game_detail(db, "learner", 4)
    app = create_app(
        db_path=path,
        project_root=tmp_path,
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    game_page = client.get("/repertoire/games/1", base_url="https://coach.invalid", headers=headers)
    assert b"Explore opening alternatives" in game_page.data
    route = f"/repertoire/games/1/openings/{first_move}"
    assert client.get(route, base_url="https://coach.invalid").status_code == 403
    for invalid in (0, 2**63):
        assert (
            client.get(
                f"/repertoire/games/{invalid}/openings/{first_move}",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/repertoire/games/1/openings/{invalid}",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 404
        )
    response = client.get(route, base_url="https://coach.invalid", headers=headers)
    assert response.status_code == 200 and b"Nf3" in response.data
    assert b"No qualified same-search comparison" in response.data
    assert b"See public reference games for this position" in response.data

    # The authenticated form queues one immutable source-bound request. GET never
    # starts the engine; a later worker completes it once and recovers its result.
    import chess_coach.opening_queue_binding as queue_binding
    import chess_coach.opening_queue_worker as queue_worker

    monkeypatch.setattr(
        queue_binding, "_config", lambda *args: ("engine", {"engine_path": "engine"})
    )
    with client.session_transaction(base_url="https://coach.invalid") as browser_session:
        csrf = browser_session["csrf"]
    post_headers = {**headers, "Origin": "https://coach.invalid"}
    form = {"csrf": csrf, "alternative": "g1f3"}
    compare_route = route + "/compare"
    assert (
        client.post(compare_route, data=form, base_url="https://coach.invalid").status_code == 403
    )
    assert (
        client.post(
            compare_route, data=form, base_url="https://coach.invalid", headers=headers
        ).status_code
        == 403
    )
    before = len(engine_calls)

    # Waitress runs requests off the main thread; its SQLite connection and
    # deadline guard must work there without using process signals.
    from concurrent.futures import ThreadPoolExecutor

    def threaded_request():
        browser = app.test_client()
        page = browser.get(route, base_url="https://coach.invalid", headers=headers)
        with browser.session_transaction(base_url="https://coach.invalid") as session:
            threaded_csrf = session["csrf"]
        sent = browser.post(
            compare_route,
            data={"csrf": threaded_csrf, "alternative": "g1f3"},
            base_url="https://coach.invalid",
            headers=post_headers,
        )
        shown = browser.get(route, base_url="https://coach.invalid", headers=headers)
        return page.status_code, sent.status_code, b"Comparison queued" in shown.data

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(threaded_request).result() == (200, 302, True)
    assert len(engine_calls) == before
    assert (
        client.post(
            compare_route, data=form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 302
    )
    assert (
        client.post(
            compare_route, data=form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 302
    )
    queued = client.get(route, base_url="https://coach.invalid", headers=headers)
    assert b"Comparison queued" in queued.data and len(engine_calls) == before
    second_route = f"/repertoire/games/2/openings/{transposed_move}/compare"
    assert (
        client.post(
            second_route,
            data={"csrf": csrf, "alternative": "d2d4"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 409
    )
    queue_worker.run(db, config, tmp_path)
    assert len(engine_calls) == before + 1
    queue_worker.run(db, config, tmp_path)
    assert len(engine_calls) == before + 1
    completed = client.get(route, base_url="https://coach.invalid", headers=headers)
    assert b"Selected comparison" in completed.data and b"120 cp" in completed.data
    assert len(engine_calls) == before + 1

    import copy

    import chess_coach.opening_queue_artifact as queue_artifact
    from chess_coach.opening_queue_proof import complete as qualified

    queued_slot = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    artifact = queue_artifact.load(planning_dir, queued_slot)
    result_body = artifact["result"]
    assert qualified(result_body, queued_slot["source"], chess.Board())
    invalid_work = copy.deepcopy(result_body)
    invalid_work["work"]["nodes"] = 200001
    assert not qualified(invalid_work, queued_slot["source"], chess.Board())
    invalid_work["work"]["nodes"] = None
    assert not qualified(invalid_work, queued_slot["source"], chess.Board())
    invalid_envelope = {"measurement": copy.deepcopy(artifact)}
    invalid_envelope["measurement"]["version"] = "unsupported"
    invalid_envelope["sha256"] = digest(canonical(invalid_envelope["measurement"]))
    with monkeypatch.context() as patch:
        patch.setattr(queue_artifact, "read", lambda path: invalid_envelope)
        with pytest.raises(ValueError, match="version"):
            queue_artifact.load(planning_dir, queued_slot)

    # Replacing the slot preserves completed history and bounded prior attempts.
    second_form = {"csrf": csrf, "alternative": "d2d4"}
    second_page = f"/repertoire/games/2/openings/{transposed_move}"
    assert (
        client.post(
            second_route, data=second_form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 302
    )
    monkeypatch.setattr(
        opening_measure,
        "measure",
        lambda *args: {"status": "insufficient", "reason": "engine_timeout"},
    )
    for attempt in range(3):
        queue_worker.run(db, config, tmp_path)
        unavailable = client.get(second_page, base_url="https://coach.invalid", headers=headers)
        assert b"Comparison unavailable" in unavailable.data
        if attempt < 2:
            assert b">Retry</button>" in unavailable.data
            assert (
                client.post(
                    second_route,
                    data={**second_form, "retry": "1"},
                    base_url="https://coach.invalid",
                    headers=post_headers,
                ).status_code
                == 302
            )
    assert b"retry limit was reached" in unavailable.data
    assert b">Retry</button>" not in unavailable.data
    earlier = client.get(route, base_url="https://coach.invalid", headers=headers)
    assert b"Selected comparison" in earlier.data and b"120 cp" in earlier.data
    assert (
        client.post(
            compare_route,
            data={**form, "retry": "1"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 302
    )
    slot = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    assert slot["attempt"] == 0
    queue_worker.run(db, config, tmp_path)
    assert len(engine_calls) == before + 1
    assert (
        client.post(
            second_route,
            data={**second_form, "retry": "1"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            second_route, data=second_form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 302
    )
    slot = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    assert slot["attempt"] == 2
    monkeypatch.setattr(
        queue_binding, "_config", lambda *args: ("engine", {"engine_path": "changed"})
    )
    changed_page = client.get(second_page, base_url="https://coach.invalid", headers=headers)
    assert b"comparison is stale" in changed_page.data
    monkeypatch.setattr(
        queue_binding, "_config", lambda *args: ("engine", {"engine_path": "engine"})
    )
    monkeypatch.setattr(opening_measure, "measure", real_measure)

    # Changed engine policy is rejected before the queued worker starts a search.
    black_route = f"/repertoire/games/3/openings/{black_move}/compare"
    assert (
        client.post(
            black_route,
            data={"csrf": csrf, "alternative": "g8f6"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 302
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            opening_measure, "_config", lambda *args: ("engine", {"engine_path": "changed"})
        )
        queue_worker.run(db, config, tmp_path)
    assert len(engine_calls) == before + 1
    black_page = client.get(
        f"/repertoire/games/3/openings/{black_move}",
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert b"Comparison unavailable" in black_page.data
    failed_slot = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    receipt = planning_dir / f"opening-comparison-{failed_slot['id']}-0.failed.json"
    failure = json.loads(receipt.read_text())["failure"]
    assert failure["status"] == "unavailable" and "score" not in failure
    # Replacing the slot cannot erase the failed attempt or restart it at zero.
    assert (
        client.post(
            compare_route, data=form, base_url="https://coach.invalid", headers=post_headers
        ).status_code
        == 302
    )
    revisited = client.get(
        f"/repertoire/games/3/openings/{black_move}",
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert b"Comparison unavailable" in revisited.data
    assert (
        client.post(
            black_route,
            data={"csrf": csrf, "alternative": "g8f6", "retry": "1"},
            base_url="https://coach.invalid",
            headers=post_headers,
        ).status_code
        == 302
    )
    retried = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    assert retried["attempt"] == 1

    import hashlib

    import chess_coach.opening_reference_source as reference_source
    from chess_coach.opening_reference_index import build as build_reference
    from chess_coach.opening_reference_read import matches as reference_matches
    from chess_coach.opening_reference_url import game_site, site

    assert not site("https://[invalid/broadcast")
    assert not site("https://lichess.org/broadcast/x/../abcdefgh")
    assert not game_site("https://lichess.org/broadcast/example/series/abcdefgh")
    assert game_site("https://lichess.org/broadcast/example/series/abcdefgh/ABCDEFGH/").endswith(
        "ABCDEFGH"
    )
    reference_dir = tmp_path / ".runtime" / "planning"
    reference_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    archive = reference_dir / reference_source.SOURCE_NAME
    archive.write_bytes(b"synthetic archive")
    with pytest.raises(ValueError, match="pinned source"):
        build_reference(tmp_path, "learner")
    sample = (
        game("Public A", "Public B", "1. d4 d5 2. Nf3 Nf6 3. c4")
        + "\n"
        + game("Public C", "Public D", "1. Nf3 Nf6 2. d4 d5 3. g3")
    )
    sample += "\n" + game("Public A", "Public B", "1. d4 d5 2. Nf3 Nf6 3. c4")
    sample = sample.replace(
        '[Event "Fixture"]',
        '[GameURL "https://lichess.org/broadcast/example/series/abcdefgh/ABCDEFGH"]\n[Event "Fixture"]',
        1,
    )
    sample = sample.replace("[GameURL ", '[UTCDate "2026.01.02"]\n[GameURL ', 1)
    same_url = game("Changed", "Names", "1. e4 e5").replace(
        '[Event "Fixture"]',
        '[GameURL "https://lichess.org/broadcast/example/series/abcdefgh/ABCDEFGH"]\n[Event "Other"]',
    )
    sample += "\n" + same_url
    sample += "\n" + game("Bad", "Game", "1. e4 e5", "*")
    sample += "\n" + game("Bad", "Mate", "1. f3 e5 2. g4 Qh4#", "1-0")
    with monkeypatch.context() as patch:
        patch.setattr(reference_source, "SOURCE_BYTES", len(archive.read_bytes()))
        patch.setattr(
            reference_source, "SOURCE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
        )
        patch.setattr(reference_source, "_decode", lambda file: (sample.encode(), False))
        coverage = build_reference(tmp_path, "learner")
        assert coverage["accepted"] == 2 and coverage["duplicates"] == 2
        assert coverage["excluded"] == 2
        with pytest.raises(ValueError, match="already exists"):
            build_reference(tmp_path, "learner")
    matching = reference_matches(tmp_path, "learner", branch_first["catalog"]["parent"])
    assert len(matching["items"]) == 2
    assert any(item["context"]["Date"] == "2026.01.02" for item in matching["items"])
    assert {item["san"] for item in matching["items"]} == {"c4", "g3"}
    ref_response = client.get(
        route + "/references", base_url="https://coach.invalid", headers=headers
    )
    assert ref_response.status_code == 200 and b"bounded convenience sample" in ref_response.data
    assert b"Public A" in ref_response.data and b"CC BY-SA 4.0" in ref_response.data
    assert b"https://lichess.org/broadcast/example/series/abcdefgh/ABCDEFGH" in ref_response.data
    assert client.get(route + "/references", base_url="https://coach.invalid").status_code == 403

    def sample_comparison(_db, _learner, _context, _board, items):
        items[0]["analysis"] = {"played": 5, "alternative": 10, "depth": 8, "line": ["Nf3"]}
        return {
            "status": "available",
            "engine": "Fixture",
            "engine_version": "1",
            "run_id": 1,
            "limits": {"nodes": 1000},
        }

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.opening_decision.comparison", sample_comparison)
        compared = client.get(route, base_url="https://coach.invalid", headers=headers)
        assert compared.status_code == 200 and b"Played 5 cp; alternative 10 cp" in compared.data
        assert b"Recorded continuation: Nf3" in compared.data
    assert (
        client.get(
            f"/repertoire/games/4/openings/{first_move}",
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 404
    )
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
    # Recompute the checked-in graph pin from the checksum-verified bundled data.
    from chess_coach.opening_snapshot import GRAPH_SHA256, import_snapshot

    reference = Database(":memory:")
    reference.initialize()
    assert import_snapshot(reference) == 3865
    reference_id = reference.connection.execute("SELECT id FROM opening_datasets").fetchone()[0]
    assert digest(canonical(opening_graph(reference, reference_id))) == GRAPH_SHA256
    reference.close()
