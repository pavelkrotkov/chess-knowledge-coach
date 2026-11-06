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
        "eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\nA04\tAlternate\tNf3 Nf6 d4 d5\nD20\tOther\td4 Nf6 c4\nD30\tC line\td4 d5 Nf3 Nf6 c4\nA10\tG line\tNf3 Nf6 d4 d5 g3\nD31\tE line\td4 d5 Nf3 Nf6 e3\n"
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

            def variation(root):
                line = [root]
                replay = board.copy()
                replay.push(root)
                for _ in range(2):
                    move = next(iter(replay.legal_moves))
                    line.append(move)
                    replay.push(move)
                return line

            return [
                {
                    "pv": variation(root_moves[0]),
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "depth": 12,
                    "nodes": 100000,
                },
                {
                    "pv": variation(root_moves[1]),
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
    experiment_url = route + "/experiment/g1f3"
    assert (
        client.get(experiment_url, base_url="https://coach.invalid", headers=headers).status_code
        == 404
    )
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
    assert b"Rehearse this opening experiment" in completed.data
    experiment = client.get(experiment_url, base_url="https://coach.invalid", headers=headers)
    assert experiment.status_code == 200
    assert b"played 0 cp; alternative 120 cp" in experiment.data
    assert b"choose Nf3" in experiment.data
    assert b"Reveal your continuation" in experiment.data
    assert b"Overall soundness and personal fit remain unknown" in experiment.data
    assert b"alternative=g1f3" in experiment.data
    assert client.get(experiment_url, base_url="https://coach.invalid").status_code == 403
    assert (
        client.get(
            route + "/experiment/e2e4", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )
    download = client.get(
        experiment_url + "?download=1", base_url="https://coach.invalid", headers=headers
    )
    assert download.status_code == 200 and download.mimetype == "application/x-chess-pgn"
    assert "no-store" in download.headers["Cache-Control"]
    import io

    import chess.pgn

    chapter = chess.pgn.read_game(io.StringIO(download.get_data(as_text=True)))
    assert chapter is not None
    assert (
        not chapter.errors
        and chapter.headers["White"] == "White"
        and chapter.headers["Black"] == "Black"
    )
    alternative_node = next(node for node in chapter.variations if node.move.uci() == "g1f3")
    reply = alternative_node.variations[0].san()
    assert f"After {reply}".encode() in experiment.data
    assert f"after {reply}" in chapter.comment
    assert {node.move.uci() for node in chapter.variations} == {"d2d4", "g1f3"}
    assert all(3 <= len(list(node.mainline_moves())) + 1 <= 4 for node in chapter.variations)
    assert len(engine_calls) == before + 1
    assert b"Preview an opening revision course" in experiment.data
    course_url = experiment_url + "/course"
    assert client.get(course_url, base_url="https://coach.invalid").status_code == 403
    import chess_coach.web_opening_course as course_view
    from chess_coach.tactical_course_budget import PreviewUnavailable
    from chess_coach.tactical_course_deadline import PreviewDeadline

    for error, status in (
        (PreviewUnavailable("deadline"), 503),
        (PreviewDeadline(), 503),
        (OSError("temporary I/O failure"), 503),
        (RuntimeError("deep engine is unavailable"), 503),
        (ValueError("source unavailable"), 404),
        (RuntimeError("unexpected failure"), 500),
    ):
        with monkeypatch.context() as patch:

            def fail(*_args, _error=error, **_kwargs):
                raise _error

            patch.setattr(course_view, "preview", fail)
            failed = client.get(course_url, base_url="https://coach.invalid", headers=headers)
        assert failed.status_code == status
    partial_course = client.get(course_url, base_url="https://coach.invalid", headers=headers)
    assert partial_course.status_code == 200 and b"Partial preview" in partial_course.data
    assert b"You play White" in partial_course.data and b'class="board"' in partial_course.data
    assert b"played 0 cp; alternative 120 cp" in partial_course.data
    assert b"Your worked comparison" in partial_course.data
    import re

    partial_version_match = re.search(
        r"Preview version: <code>([0-9a-f]{64})</code>", partial_course.get_data(as_text=True)
    )
    assert partial_version_match
    partial_version = partial_version_match.group(1)
    assert (
        client.get(
            course_url + "?download=1", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 409
    )
    partial_download = client.get(
        course_url + "?download=1&version=" + partial_version,
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert (
        partial_download.status_code == 200
        and "no-store" in partial_download.headers["Cache-Control"]
    )
    partial_stream = io.StringIO(partial_download.get_data(as_text=True))
    assert chess.pgn.read_game(partial_stream) is not None
    assert chess.pgn.read_game(partial_stream) is None

    import copy

    import chess_coach.opening_queue_artifact as queue_artifact
    from chess_coach.opening_queue_proof import complete as qualified

    queued_slot = json.loads((planning_dir / "opening-comparison-slot.json").read_text())
    artifact = queue_artifact.load(planning_dir, queued_slot)
    result_body = artifact["result"]
    assert qualified(result_body, queued_slot["source"], chess.Board())
    from chess_coach.opening_experiment import qualified as experiment_qualified

    choice = next(item for item in first["catalog"]["items"] if item["uci"] == "g1f3")
    borderline = copy.deepcopy(result_body)
    played_line = next(line for line in borderline["lines"] if line["root_move"] == "d2d4")
    alternate_line = next(line for line in borderline["lines"] if line["root_move"] == "g1f3")
    alternate_line["score_value"] = played_line["score_value"] - 50
    assert experiment_qualified(first, choice, borderline)
    alternate_line["score_value"] -= 1
    assert experiment_qualified(first, choice, borderline) is None
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.opening_experiment_current.statuses", lambda *_args: {"g1f3": borderline}
        )
        assert (
            client.get(
                experiment_url, base_url="https://coach.invalid", headers=headers
            ).status_code
            == 404
        )
    alternate_line["score_value"] += 1
    alternate_line["pv"] = "g1f3 g8f6"
    assert experiment_qualified(first, choice, borderline) is None
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
    assert (
        client.get(experiment_url, base_url="https://coach.invalid", headers=headers).status_code
        == 404
    )
    assert (
        client.get(
            experiment_url + "?download=1", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get(course_url, base_url="https://coach.invalid", headers=headers).status_code == 404
    )
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
    # Build a separate ordered index from the same synthetic pinned archive.

    import chess_coach.opening_profile_lookup as profile_lookup
    from chess_coach.opening_profile_index import INDEX_NAME as PROFILE_INDEX
    from chess_coach.opening_profile_index import build as build_profile
    from chess_coach.opening_profile_read import profile as read_profile
    from chess_coach.opening_reference_index import INDEX_NAME as REFERENCE_INDEX
    from chess_coach.opening_storage import position_key

    french = game(
        "Public E",
        "Public F",
        "1. e4 e6 2. d4 d5 3. e5 c5 4. Nf3 Nc6 5. Ng1 Nb8 6. Nf3 Nc6 7. Nc3 Bd7",
    )
    black_french = game("Public G", "Public H", "1. e3 e5 2. d4 d5 3. c4 e4")
    repeated = game("Repeater", "Public I", "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. g3")
    french_copy = french.replace('[Event "Fixture"]', '[Event "Other event"]')
    center_game = game("Central", "Capture", "1. d4 d5 2. e4 dxe4")
    inconsistent_game = game("Inconsistent", "Opponent", "1. d4 d5 2. Nf3 Nf6")
    owned_alt = next(line for line in result_body["lines"] if line["root_move"] == "g1f3")
    duplicate_game = chess.pgn.Game()
    duplicate_game.headers["White"] = "Public duplicate"
    duplicate_game.headers["Black"] = "Public opponent"
    duplicate_game.headers["Result"] = "1-0"
    replay = chess.Board()
    node = duplicate_game
    for text in owned_alt["pv"].split():
        move = replay.parse_uci(text)
        node = node.add_variation(move)
        replay.push(move)
    node.add_variation(next(iter(replay.legal_moves)))
    profile_sample = (
        str(duplicate_game)
        + "\n\n"
        + sample
        + "\n"
        + french
        + "\n"
        + french_copy
        + "\n"
        + black_french
        + "\n"
        + repeated
        + "\n"
        + center_game
        + "\n"
        + inconsistent_game
    )
    for index in range(11):
        profile_sample += "\n" + game(f"Sample {index}", f"Opponent {index}", "1. Nf3 Nf6")
    old_index = reference_dir / REFERENCE_INDEX
    old_hash = hashlib.sha256(old_index.read_bytes()).hexdigest()
    import chess_coach.opening_profile_index as profile_index

    original_moves_for = profile_index.moves_for

    def one_inconsistent(game_value):
        result = original_moves_for(game_value)
        if game_value.headers.get("White") == "Inconsistent":
            moves, positions = result
            ply, _parent, san, uci, shapes = positions[1]
            positions[1] = (ply, position_key(chess.Board()), san, uci, shapes)
            return moves, positions
        return result

    with monkeypatch.context() as patch:
        patch.setattr(reference_source, "SOURCE_BYTES", len(archive.read_bytes()))
        patch.setattr(
            reference_source, "SOURCE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
        )
        patch.setattr(reference_source, "_decode", lambda file: (profile_sample.encode(), False))
        patch.setattr(profile_index, "moves_for", one_inconsistent)
        ordered_coverage = build_profile(tmp_path, "learner")
        assert (ordered_coverage["accepted"], ordered_coverage["duplicates"]) == (19, 3), (
            ordered_coverage["accepted"],
            ordered_coverage["duplicates"],
            ordered_coverage["examined"],
        )
        with pytest.raises(ValueError, match="already exists"):
            build_profile(tmp_path, "learner")
    assert hashlib.sha256(old_index.read_bytes()).hexdigest() == old_hash
    start_key = position_key(chess.Board())
    white_profile = read_profile(tmp_path, "learner", start_key, "e2e4")
    assert white_profile["games"] == 1
    assert any(
        shape["family"] == "french_advance" and shape["color"] == "white" and shape["count"] == 1
        for shape in white_profile["families"]
    )
    assert white_profile["short_windows"] == 0 and white_profile["window_cutoffs"] == 1
    black_profile = read_profile(tmp_path, "learner", start_key, "e2e3")
    assert black_profile["games"] == 1 and black_profile["short_windows"] == 1
    assert any(
        shape["family"] == "french_advance" and shape["color"] == "black" and shape["count"] == 1
        for shape in black_profile["families"]
    )
    ordered_path = reference_dir / PROFILE_INDEX
    with sqlite3.connect(ordered_path.as_uri() + "?mode=ro", uri=True) as ordered:
        repeater_id = next(
            row[0]
            for row in ordered.execute("SELECT id,context FROM games")
            if json.loads(row[1])["White"] == "Repeater"
        )
        occurrences = ordered.execute(
            "SELECT ply FROM moves WHERE game_id=? AND parent=? AND uci=? ORDER BY ply",
            (repeater_id, start_key, "g1f3"),
        ).fetchall()
    assert occurrences == [(1,), (5,)]
    repeated_profile = read_profile(tmp_path, "learner", start_key, "g1f3")
    assert repeated_profile["games"] == 10 and repeated_profile["more_matches"]
    assert (
        next(
            item for item in repeated_profile["examples"] if item["context"]["White"] == "Repeater"
        )["first_ply"]
        == 1
    )
    empty_profile = read_profile(tmp_path, "learner", start_key, "e2e5")
    assert empty_profile["games"] == 0 and empty_profile["center"]["valid"] == 0
    d4_profile = read_profile(tmp_path, "learner", start_key, "d2d4")
    assert d4_profile["games"] == 3
    assert d4_profile["center"]["valid"] == 2
    assert d4_profile["center"]["capture"] == 1
    assert d4_profile["center"]["inconsistent"] == 1
    assert repeated_profile["center"]["short"] > 0
    for profile in (d4_profile, repeated_profile, empty_profile):
        center = profile["center"]
        assert (
            sum(center[key] for key in ("valid", "short", "inconsistent", "unavailable"))
            == profile["games"]
        )

    from chess_coach.opening_profile_center_replay import inspect as center_window

    def ordered_window(board, moves):
        parent = position_key(board)
        rows = []
        for ply, text in enumerate(moves, 1):
            move = board.parse_uci(text)
            rows.append((ply, position_key(board), text, board.san(move)))
            board.push(move)
        return rows, parent

    recapture_board = chess.Board()
    for text in ("e2e4", "d7d5", "e4d5"):
        recapture_board.push_uci(text)
    recapture_moves = ["e7e6", "d5e6", "f7e6", "g1f3"]
    recapture_rows, recapture_parent = ordered_window(recapture_board, recapture_moves)
    state, central = center_window(recapture_rows, 1, 4, recapture_parent, recapture_moves[0])
    assert state == "valid" and central["capture"] and central["recapture"]
    bad_rows = list(recapture_rows)
    ply, parent, _uci, _san = bad_rows[1]
    bad_rows[1] = (ply, parent, "0000", "--")
    assert center_window(bad_rows, 1, 4, recapture_parent, recapture_moves[0])[0] == "inconsistent"
    assert (
        center_window(recapture_rows[:3], 1, 4, recapture_parent, recapture_moves[0])[0]
        == "inconsistent"
    )
    assert (
        center_window(recapture_rows[:3], 1, 3, recapture_parent, recapture_moves[0])[0] == "short"
    )

    opening_board = chess.Board("4k3/8/4p3/3P4/8/8/8/4K3 w - - 0 1")
    opening_moves = ["d5e6", "e8e7", "e1d2", "e7e6"]
    opening_rows, opening_parent = ordered_window(opening_board, opening_moves)
    state, central = center_window(opening_rows, 1, 4, opening_parent, opening_moves[0])
    assert state == "valid" and central["opened_d"] and central["opened_e"]
    with monkeypatch.context() as patch:
        patch.setattr(profile_lookup, "GRAPH_SHA256", "different")
        assert read_profile(tmp_path, "learner", start_key, "e2e4") is None
    with monkeypatch.context() as patch:
        patch.setattr(profile_lookup, "SOURCE_SHA256", "different")
        assert read_profile(tmp_path, "learner", start_key, "e2e4") is None

    import chess_coach.opening_profile_read as profile_read

    nonfile = reference_dir / "not-an-index"
    nonfile.mkdir(mode=0o700)
    with monkeypatch.context() as patch:
        patch.setattr(profile_read, "INDEX_NAME", nonfile.name)
        assert read_profile(tmp_path, "learner", start_key, "e2e4") is None

    profile_url = route + "/profile"
    assert client.get(profile_url, base_url="https://coach.invalid").status_code == 403
    before_profile = len(engine_calls)
    profile_page = client.get(profile_url, base_url="https://coach.invalid", headers=headers)
    assert profile_page.status_code == 200
    assert (
        b"Your played move" in profile_page.data
        and b"One legal catalog alternative" in profile_page.data
    )
    assert (
        b"bounded convenience sample" in profile_page.data
        and b"Broadcast source" in profile_page.data
    )
    assert profile_lookup.SOURCE_SHA256.encode() in profile_page.data
    assert b"Among 2 complete, legally consistent four-ply windows" in profile_page.data
    assert b"1 contained a central pawn-on-pawn capture" in profile_page.data
    assert b"1 had inconsistent ordered moves" in profile_page.data
    assert b"had a shorter valid window" in profile_page.data
    assert b"played 0 cp; alternative 120 cp" in profile_page.data
    selected_profile = client.get(
        profile_url + "?alternative=g1f3", base_url="https://coach.invalid", headers=headers
    )
    assert (
        b"Selected catalog alternative" in selected_profile.data and b"Nf3" in selected_profile.data
    )
    assert (
        client.get(
            profile_url + "?alternative=e2e4", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )
    assert len(engine_calls) == before_profile

    # The version changes when a distinct public chapter becomes available;
    # downloads are bound to the exact preview currently shown.
    read_only = Database(path)
    statements = []
    read_only.connection.set_trace_callback(
        lambda sql: statements.append(sql.split(None, 1)[0].upper())
    )
    before_files = {
        item.name: (item.stat().st_size, item.stat().st_mtime_ns)
        for item in reference_dir.iterdir()
        if item.is_file()
    }
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_opening_course.database", lambda: read_only)
        course = client.get(course_url, base_url="https://coach.invalid", headers=headers)
    read_only.close()
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)
    after_files = {
        item.name: (item.stat().st_size, item.stat().st_mtime_ns)
        for item in reference_dir.iterdir()
        if item.is_file()
    }
    assert after_files == before_files
    assert course.status_code == 200 and b"2. Public continuation" in course.data
    assert b"CC BY-SA 4.0" in course.data and b"same position" in course.data
    version_match = re.search(
        r"Preview version: <code>([0-9a-f]{64})</code>", course.get_data(as_text=True)
    )
    assert version_match
    course_version = version_match.group(1)
    assert course_version != partial_version
    repeated_course = client.get(course_url, base_url="https://coach.invalid", headers=headers)
    assert course_version.encode() in repeated_course.data
    assert (
        client.get(
            course_url + "?download=1&version=" + partial_version,
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 409
    )
    exported = client.get(
        course_url + "?download=1&version=" + course_version,
        base_url="https://coach.invalid",
        headers=headers,
    )
    assert exported.status_code == 200 and "no-store" in exported.headers["Cache-Control"]
    stream = io.StringIO(exported.get_data(as_text=True))
    owned_chapter = chess.pgn.read_game(stream)
    public_chapter = chess.pgn.read_game(stream)
    assert owned_chapter is not None and public_chapter is not None
    assert chess.pgn.read_game(stream) is None
    assert not owned_chapter.errors and not public_chapter.errors
    assert all(
        game_value.headers["White"] == "White" and game_value.headers["Black"] == "Black"
        for game_value in (owned_chapter, public_chapter)
    )
    public_moves = [move.uci() for move in public_chapter.mainline_moves()]
    assert len(public_moves) == 4 and public_moves[0] == "g1f3"
    assert public_moves[: len(owned_alt["pv"].split())] != owned_alt["pv"].split()
    import chess_coach.opening_course_public_lookup as course_lookup

    with monkeypatch.context() as patch:
        patch.setattr(course_lookup, "MAX_GAMES", 1)
        duplicate_only = client.get(course_url, base_url="https://coach.invalid", headers=headers)
    assert (
        b"Partial preview" in duplicate_only.data
        and b"no distinct continuation" in duplicate_only.data
    )
    assert position_key(public_chapter.board()) == position_key(owned_chapter.board())
    assert "CC BY-SA 4.0" in public_chapter.comment
    assert "https://database.lichess.org/" in public_chapter.comment
    assert len(engine_calls) == before_profile

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

    # The lazy branch uses pre-move identity and independently replayed games.
    import chess_coach.opening_explore_verify as explore_verify
    from chess_coach.opening_explore import explore

    before_explore = len(engine_calls)
    branch_url = "/repertoire/explore"
    assert client.get(branch_url, base_url="https://coach.invalid").status_code == 403
    branch_page = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
    assert branch_page.status_code == 200
    assert b"2 distinct game identities verified" in branch_page.data
    assert b"Played c4" in branch_page.data and b"Played g3" in branch_page.data
    assert b"legal catalog alternative" in branch_page.data
    assert b"Public A" in branch_page.data and b"Public C" in branch_page.data
    # The score belongs to another decision even though it is from this game.
    assert b"120 cp" not in branch_page.data and len(engine_calls) == before_explore

    # Store two independently bound synthetic worker results for the actual
    # exemplar. The first is outside the threshold; the later one qualifies.
    from chess_coach.opening_queue_location import location as queue_location

    directory, database_key = queue_location(db, tmp_path, "learner")
    real_choices = branch_second["catalog"]["items"]
    assert len(real_choices) >= 2
    for index, candidate in enumerate(real_choices[:2]):
        _budget, binding, measured_config, owned = queue_binding.snapshot(
            db, database_key, "learner", 2, after_second, candidate["uci"]
        )
        item = queue_binding.request(database_key, binding, measured_config)
        board = owned["board"]
        roots = [chess.Move.from_uci(binding["played"]), chess.Move.from_uci(candidate["uci"])]
        raw = Engine().analyse(board, None, multipv=2, root_moves=roots)
        raw[1]["score"] = chess.engine.PovScore(
            chess.engine.Cp(-51 if index == 0 else 20), board.turn
        )
        measured_lines, problem = opening_grade.grade(
            board, owned["position"], [move.uci() for move in roots], raw, None
        )
        assert problem is None and measured_lines
        payload = {
            **artifact,
            "source": binding,
            "configuration": measured_config,
            "result": {**result_body, "lines": measured_lines},
        }
        envelope = {"measurement": payload, "sha256": digest(canonical(payload))}
        path_for_result = queue_artifact.path(directory, item)
        path_for_result.write_text(json.dumps(envelope))
        path_for_result.chmod(0o600)

    before_explore = len(engine_calls)
    actual_scored = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
    assert actual_scored.status_code == 200
    assert b"more than 50 cp below the played move" in actual_scored.data
    assert f"/experiment/{real_choices[0]['uci']}".encode() not in actual_scored.data
    assert f"/experiment/{real_choices[1]['uci']}".encode() in actual_scored.data
    assert f"alternative={real_choices[1]['uci']}".encode() in actual_scored.data
    assert (
        client.get(
            f"/repertoire/games/2/openings/{after_second}/experiment/{real_choices[1]['uci']}",
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 200
    )
    assert len(engine_calls) == before_explore

    import chess_coach.opening_explore_enrich as explore_enrich

    score_calls, offered = [], []

    def line_for(board, root, value):
        replay = board.copy()
        moves = [replay.parse_uci(root)]
        replay.push(moves[0])
        for _ in range(2):
            move = next(iter(replay.legal_moves))
            moves.append(move)
            replay.push(move)
        return {
            "root_move": root,
            "pv": " ".join(move.uci() for move in moves),
            "score_value": value,
            "depth": 12,
        }

    def exact_score(_db, _root, _learner, decision, *, deadline=None):
        assert deadline is not None
        score_calls.append((decision["game_id"], decision["position_id"]))
        choices = decision["catalog"]["items"]
        assert len(choices) >= 2
        offered[:] = choices
        board = chess.Board(decision["fen"])
        played = line_for(board, decision["played_uci"], 0)
        return {
            choice["uci"]: {
                "status": "complete",
                "lines": [played, line_for(board, choice["uci"], -51 if index == 0 else 20)],
            }
            for index, choice in enumerate(choices)
        }

    with monkeypatch.context() as patch:
        patch.setattr(explore_enrich, "statuses", exact_score)
        scored = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
        assert b"played 0 cp; alternative -51 cp" in scored.data
        assert b"more than 50 cp below the played move" in scored.data
        assert f"/experiment/{offered[0]['uci']}".encode() not in scored.data
        assert f"/experiment/{offered[1]['uci']}".encode() in scored.data
        assert f"alternative={offered[1]['uci']}".encode() in scored.data
        assert score_calls == [(2, after_second)]

    def short_score(*args, **kwargs):
        states = exact_score(*args, **kwargs)
        first = states[offered[0]["uci"]]
        first["lines"][1]["score_value"] = 0
        first["lines"][1]["pv"] = " ".join(first["lines"][1]["pv"].split()[:2])
        return states

    with monkeypatch.context() as patch:
        patch.setattr(explore_enrich, "statuses", short_score)
        short = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
    assert b"fewer than three plies" in short.data
    assert f"/experiment/{offered[0]['uci']}".encode() not in short.data
    assert f"/experiment/{offered[1]['uci']}".encode() in short.data
    assert len(engine_calls) == before_explore

    def queued_and_stale(_db, _root, _learner, decision, *, deadline=None):
        choices = decision["catalog"]["items"]
        return {choices[0]["uci"]: {"status": "queued"}, choices[1]["uci"]: {"status": "stale"}}

    with monkeypatch.context() as patch:
        patch.setattr(explore_enrich, "statuses", queued_and_stale)
        waiting = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
    assert b"Comparison queued" in waiting.data and b"Comparison is stale" in waiting.data
    with monkeypatch.context() as patch:
        from chess_coach.tactical_course_budget import PreviewUnavailable

        patch.setattr(
            explore_enrich,
            "statuses",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PreviewUnavailable("deadline")),
        )
        deferred_page = client.get(branch_url, base_url="https://coach.invalid", headers=headers)
    assert (
        deferred_page.status_code == 200 and b"Comparison status is unknown" in deferred_page.data
    )
    assert b"Some nominations or checks were not completed" in deferred_page.data
    assert len(engine_calls) == before_explore
    assert f"/repertoire/games/1/openings/{after_first}".encode() in branch_page.data
    assert f"/repertoire/games/2/openings/{after_second}".encode() in branch_page.data

    actual_identities = explore_verify.decisions_for_game

    def duplicate_game(*args):
        identities = actual_identities(*args)
        assert identities is not None
        for item in identities.values():
            item["game_key"] = "same-game"
        return identities

    with monkeypatch.context() as patch:
        patch.setattr(explore_verify, "decisions_for_game", duplicate_game)
        duplicate = explore(db, "learner")
        assert duplicate["branch"] is None and duplicate["duplicates"] >= 1
    with monkeypatch.context() as patch:
        patch.setattr(
            explore_verify,
            "classification",
            lambda *args: (_ for _ in ()).throw(ValueError("stale")),
        )
        stale_branch = explore(db, "learner")
        assert stale_branch["branch"] is None and stale_branch["unavailable"] >= 1

    from chess_coach.opening_explore_nomination import _game as nominate_game
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with monkeypatch.context() as patch:
        patch.setattr(
            explore_verify,
            "classification",
            lambda *args: (_ for _ in ()).throw(PreviewUnavailable("deferred")),
        )
        deferred = explore(db, "learner")
        assert deferred["branch"] is None and deferred["deferred"] >= 1 and deferred["partial"]

    # Different castling rights are distinct metadata positions.
    black_to_move = chess.Board()
    black_to_move.push_uci("e2e4")
    no_rights = black_to_move.copy()
    no_rights.castling_rights = 0
    next_position = {"id": 2, "ply": 4, "fen": black_to_move.fen()}
    first = {"id": 1, "ply": 3, "fen": black_to_move.fen()}
    other = {**first, "fen": no_rights.fen()}
    sample_game = {"id": 1, "projected_start": "2026-01-01"}
    assert (
        nominate_game(sample_game, "black", [first, next_position])[0][0]
        != nominate_game(sample_game, "black", [other, next_position])[0][0]
    )
    assert not nominate_game(sample_game, "white", [first, next_position])

    # Two real import records of the same synthetic game do not form a branch.
    duplicate_db = Database(tmp_path / "duplicate-fixture.sqlite")
    duplicate_db.initialize()
    duplicate_text = game("Learner", "Opponent", "1. d4 d5 2. Nf3 Nf6 3. c4", second=3)
    ingest_pgn(duplicate_db, duplicate_text, source="fixture-a")
    ingest_pgn(duplicate_db, duplicate_text, source="fixture-b")
    import_openings(duplicate_db, source, version="test", source_url="cc0://test")
    for game_id in (1, 2):
        run_opening(duplicate_db, game_id, game_input(duplicate_db, game_id), config)
    only_duplicate = explore(duplicate_db, "learner")
    assert only_duplicate["branch"] is None and only_duplicate["duplicates"] >= 1
    ingest_pgn(
        duplicate_db,
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5 3. g3", "0-1", second=3),
        source="fixture-c",
    )
    run_opening(duplicate_db, 3, game_input(duplicate_db, 3), config)
    independent = explore(duplicate_db, "learner")
    assert len(independent["branch"]["games"]) == 2 and independent["duplicates"] >= 1

    # Oversized PGN text is excluded before reprojection or Python loading.
    oversized = duplicate_text.replace("1. d4", "{" + "\x00" + "x" * 1_000_001 + "} 1. d4")
    ingest_pgn(duplicate_db, oversized, source="fixture-oversized")
    from chess_coach.opening_explore_recent import recent as bounded_recent

    bounded_games, bounded_coverage = bounded_recent(duplicate_db, "learner")
    assert (
        duplicate_db.connection.execute(
            "SELECT instr(CAST(pgn AS BLOB),X'00') FROM games WHERE source='fixture-oversized'"
        ).fetchone()[0]
        > 0
    )
    assert len(bounded_games) == 3 and bounded_coverage["oversized_pgn"] == 1
    assert all(set(game) == {"id", "projected_start"} for game, _ in bounded_games)
    assert bounded_coverage["candidate_recheck_failed"] >= 1

    # A repeated position after the last named match is not nominated.
    short_source = tmp_path / "short-opening.tsv"
    short_source.write_text("eco\tname\tmoves\nD00\tEarlier\td4 d5 Nf3 Nf6\n")
    boundary_db = Database(tmp_path / "boundary-fixture.sqlite")
    boundary_db.initialize()
    ingest_pgn(boundary_db, duplicate_text, source="fixture-a")
    ingest_pgn(boundary_db, duplicate_text, source="fixture-b")
    ingest_pgn(
        boundary_db,
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5 3. g3", "0-1", second=3),
        source="fixture-c",
    )
    import_openings(boundary_db, short_source, version="test", source_url="cc0://test")
    for game_id in (1, 2, 3):
        run_opening(boundary_db, game_id, game_input(boundary_db, game_id), config)
    short_graph = opening_graph(boundary_db, 1)
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.opening_decision_budget.GRAPH_SHA256", digest(canonical(short_graph))
        )
        after_boundary = explore(boundary_db, "learner")
        assert after_boundary["branch"] is None and after_boundary["nominations"] == 0

        # Oversized stored FENs are SQL-truncated before any chess parser sees them.
        boundary_db.connection.execute(
            "UPDATE positions SET fen=fen || ? WHERE game_id=3 AND ply=3",
            ("\x00" + "x" * 1_000_001,),
        )
        boundary_db.connection.commit()
        import chess_coach.opening_explore_nomination as nomination
        from chess_coach.opening_queue_budget import BrowserBudget

        original_game = nomination._game
        inspected = []
        omitted = []

        def bounded_positions(game, color, positions):
            inspected.extend(len(row["fen"] or "") for row in positions)
            omitted.extend(row["fen"] is None for row in positions)
            return original_game(game, color, positions)

        patch.setattr(nomination, "_game", bounded_positions)
        rows, coverage_after = bounded_recent(boundary_db, "learner")
        assert rows, coverage_after
        nomination.candidates(boundary_db, rows, BrowserBudget(boundary_db))
        assert inspected and max(inspected) <= 200 and any(omitted)
        assert (
            boundary_db.connection.execute(
                "SELECT instr(CAST(fen AS BLOB),X'00') FROM positions WHERE game_id=3 AND ply=3"
            ).fetchone()[0]
            > 0
        )
        patch.setattr(explore_verify, "classification", lambda *_: pytest.fail("unbounded replay"))
        with pytest.raises(ValueError, match="input limits"):
            explore_verify.verify(
                boundary_db,
                "learner",
                ("white", "unused"),
                {"game_id": 3, "position_id": 1, "played_at": "unused"},
                BrowserBudget(boundary_db),
                {},
            )
    boundary_db.close()
    duplicate_db.close()

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
