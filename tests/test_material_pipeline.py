"""Synthetic material evidence retains current provenance and review boundaries."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.material_detector import process_decision
from chess_coach.material_observation import material_observation
from chess_coach.material_publish import publish
from chess_coach.material_source import prepare
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis

LEARNER = "fixture_learner"


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            root = root_moves[0] if root_moves else chess.Move.from_uci("d1d4")
            continuation = board.copy()
            continuation.push(root)
            reply = chess.Move.from_uci("e8f8")
            assert reply in continuation.legal_moves
            score = 0 if root_moves else 500
            moves = [root, reply]
        else:
            moves = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
            score = 0
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                "pv": moves,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def make_game(path, monkeypatch, *, timed=True, played="e1f1"):
    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    if timed:
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci("e8f8"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db


def test_unreviewed_observation_replays_and_never_enters_mastery(tmp_path, monkeypatch):
    db = make_game(tmp_path / "material.sqlite", monkeypatch)
    before = db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
    result = process_decision(db, 1, LEARNER)
    assert result["outcome"] == "failure" and len(result["evidence_ids"]) == 1
    evidence_id = result["evidence_ids"][0]
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["review_status"] == "unreviewed" and evidence["skill"] == "hanging_piece"
    assert evidence["context"]["material_observation"]["best"]["san"] == ["Rxd4", "Kf8"]
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    replay = process_decision(db, 1, LEARNER)
    assert replay["replayed"] and replay["evidence_ids"] == [evidence_id]
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    eligible, excluded = eligible_contexts(
        db, LEARNER, "hanging_piece", "execute", datetime.now(UTC)
    )
    assert len(eligible) == 1 and eligible[0]["outcome"] == "failure"
    assert not excluded
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == before


def test_source_change_supersedes_without_deleting_review(tmp_path, monkeypatch):
    db = make_game(tmp_path / "changed.sqlite", monkeypatch)
    first = process_decision(db, 1, LEARNER)
    old = first["evidence_ids"][0]
    review_evidence(db, old, decision="accept", actor="fixture_reviewer")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    second = process_decision(db, 1, LEARNER)
    assert second["evidence_ids"] != [old]
    assert inspect_evidence(db, old)["lifecycle_status"] == "superseded"
    assert inspect_evidence(db, old)["review_status"] == "accepted"
    assert inspect_evidence(db, second["evidence_ids"][0])["review_status"] == "unreviewed"


def test_atomic_publication_rejects_changed_source(tmp_path, monkeypatch):
    db = make_game(tmp_path / "race.sqlite", monkeypatch)
    prepared = prepare(db, 1, LEARNER)
    fact = material_observation(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="source changed"):
        publish(db, prepared, fact)
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer=?", ("material-opportunity",)
        ).fetchone()[0]
        == 0
    )
    assert not db.connection.in_transaction


def test_automatic_worker_records_provisional_material_and_browser_explains(tmp_path, monkeypatch):
    import httpx

    from chess_coach import material_detector
    from chess_coach.pipeline import process_pipeline
    from chess_coach.web import create_app

    path = tmp_path / "worker.sqlite"
    db = make_game(path, monkeypatch)
    original = material_detector.material_observation
    calls = []

    def observe(*args):
        assert not db.connection.in_transaction
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(material_detector, "material_observation", observe)
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_max_decisions=1,
    )
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=network)
    assert calls and result["material"]["processed"] == 1
    assert result["material"]["outcomes"]["failure"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE mapper_version=?", ("1.0.0",)
    ).fetchone()
    evidence_id = row["id"]
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    page = client.get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"tested best continuation captures material" in page.data
    assert b"Rxd4" in page.data and b"capture version 1.1.0" in page.data
    assert b"pawn-capture claims" in page.data and b"en passant" in page.data
    assert b"Material source: current" in page.data
    assert inspect_evidence(db, evidence_id)["review_status"] == "unreviewed"
    process_pipeline(db, config, transport=network)
    replay = process_pipeline(db, config, transport=network)
    assert replay["material"]["replayed"] == 1 and len(calls) == 1

    import io

    from chess_coach.material_worker import process_material

    def add_fixture_game(target, label, second, *, extended=False):
        pgn = target.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
        parsed = chess.pgn.read_game(io.StringIO(pgn))
        assert parsed is not None
        parsed.headers["Event"] = label
        parsed.headers["UTCTime"] = f"12:00:{second:02}"
        if extended:
            node = parsed.end()
            node = node.add_variation(chess.Move.from_uci("f1e1"))
            node.add_variation(chess.Move.from_uci("f8e8"))
        ingest_pgn(target, str(parsed))

    recent_db = make_game(tmp_path / "recent-material.sqlite", monkeypatch)
    add_fixture_game(recent_db, "Unanalyzed", 2)
    add_fixture_game(recent_db, "Recent analyzed", 3)
    recent_config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        material_max_scan=4,
        material_max_decisions=2,
    )
    assert (
        run_analysis(
            recent_db, 3, game_input(recent_db, 3), recent_config, engine_identity(sys.executable)
        )["status"]
        == "complete"
    )
    from dataclasses import replace

    old_config = replace(recent_config, nodes=50)
    assert (
        run_analysis(
            recent_db, 2, game_input(recent_db, 2), old_config, engine_identity(sys.executable)
        )["status"]
        == "complete"
    )
    before_outputs = recent_db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[
        0
    ]
    observations = []

    def first_has_no_fact(*args):
        observations.append(True)
        return None if len(observations) == 1 else original(*args)

    with monkeypatch.context() as patch:
        patch.setattr(material_detector, "material_observation", first_has_no_fact)
        first = process_material(recent_db, recent_config)
        assert first["recent"]["game_window"] == 40
        assert first["recent"]["scan_limit"] == 3 and first["recent"]["decision_limit"] == 1
        assert first["recent"]["games_examined"] == 1
        assert first["recent"]["no_opportunity"] == 1
        assert first["recent"]["processed"] == 1 and first["outcomes"]["failure"] == 1
        assert first["examined"] <= 4 and first["processed"] == 2
        assert first["recent"]["pending"] and first["recent"]["status"] == "pending"
        assert (
            recent_db.connection.execute(
                "SELECT COUNT(*) FROM detector_runs WHERE position_id=? AND status='active'", (5,)
            ).fetchone()[0]
            == 1
        )
        process_material(recent_db, recent_config)
        for _ in range(4):
            third = process_material(recent_db, recent_config)
            if third["recent"]["replayed"] and third["recent"]["source_unavailable"]:
                break
        assert third["recent"]["source_unavailable"] >= 1
        assert third["recent"]["status"] == "unavailable"
        assert third["status"] == (
            "partial" if third["capped"] or third["unavailable"] else "complete"
        )
        assert third["recent"]["replayed"] == 1 and third["recent"]["observed"] == 1
    assert (
        recent_db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
        == before_outputs
    )

    # A new game can become analyzed while the old recent rotation is in flight.
    from chess_coach.material_recent_cursor import load as recent_state
    from chess_coach.material_worker_cursor import scan as archive_scan

    fresh_path = tmp_path / "fresh-material.sqlite"
    fresh_db = make_game(fresh_path, monkeypatch)
    add_fixture_game(fresh_db, "Older analyzed", 2)
    minimal = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        material_max_scan=1,
        material_max_decisions=1,
    )
    run_analysis(fresh_db, 2, game_input(fresh_db, 2), minimal, engine_identity(sys.executable))
    assert process_material(fresh_db, minimal)["recent"]["pending"] is None
    rotated = process_material(fresh_db, minimal)
    assert rotated["recent"]["processed"] == 1 and recent_state(fresh_db, LEARNER)["within"]
    rotation_before = recent_state(fresh_db, LEARNER)
    add_fixture_game(fresh_db, "Newly analyzed", 3, extended=True)
    archive_before = archive_scan(fresh_db, LEARNER, 1)[1][0]["id"]
    assert process_material(fresh_db, minimal)["recent"]["pending"] is None
    assert archive_scan(fresh_db, LEARNER, 1)[1][0]["id"] > archive_before
    run_analysis(fresh_db, 3, game_input(fresh_db, 3), minimal, engine_identity(sys.executable))
    output_count = fresh_db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
    fresh_db.close()
    fresh_db = Database(fresh_path)
    archive_resume = archive_scan(fresh_db, LEARNER, 1)[1][0]["id"]
    fresh = process_material(fresh_db, minimal)
    assert fresh["recent"]["game_window"] == 10 and fresh["recent"]["processed"] == 1
    assert fresh["examined"] <= 1 and fresh["processed"] <= 1
    assert recent_state(fresh_db, LEARNER)["after"] == rotation_before["after"]
    assert recent_state(fresh_db, LEARNER)["ply"] == rotation_before["ply"]
    new_position = fresh_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=3 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    new_runs = fresh_db.connection.execute(
        "SELECT COUNT(*) FROM detector_runs WHERE position_id=?", (new_position,)
    ).fetchone()[0]
    assert new_runs == 1
    for _ in range(4):
        cycle = process_material(fresh_db, minimal)
        assert cycle["examined"] <= 1 and cycle["processed"] <= 1
    rotation_after = recent_state(fresh_db, LEARNER)
    assert not rotation_after["within"] or rotation_after["after"] != rotation_before["after"]
    assert archive_scan(fresh_db, LEARNER, 1)[1][0]["id"] > archive_resume
    assert (
        fresh_db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE position_id=?", (new_position,)
        ).fetchone()[0]
        == new_runs
    )
    assert (
        fresh_db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
        == output_count
    )
    # Exact replays stay unchanged; changed cheap lines refresh the active result.
    from collections import Counter

    from chess_coach.material_fresh import work as fresh_work
    from chess_coach.material_fresh_turn import load as fresh_state
    from chess_coach.material_fresh_turn import save as save_fresh_state
    from chess_coach.material_worker import _recent_report

    def tick(target):
        report = {"examined": 0, "processed": 0, "replayed": 0, "unavailable": 0}
        recent = _recent_report()
        used = fresh_work(
            target,
            minimal,
            engine_identity(sys.executable),
            report,
            Counter(),
            recent,
            1,
            1,
            fresh_state(target, LEARNER),
        )
        assert report["examined"] <= 1 and report["processed"] <= 1
        return used, report, recent

    state = fresh_state(fresh_db, LEARNER)
    save_fresh_state(
        fresh_db,
        LEARNER,
        {**state, "positions": [item for item in state["positions"] if item[0] != 3]},
    )
    used, _report, recent = tick(fresh_db)
    assert new_position in used and recent["replayed"] == 1
    fresh_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=? AND role=?",
        (new_position, "best"),
    )
    fresh_db.connection.commit()
    state = fresh_state(fresh_db, LEARNER)
    save_fresh_state(
        fresh_db,
        LEARNER,
        {**state, "positions": [item for item in state["positions"] if item[0] != 3]},
    )
    used, _report, recent = tick(fresh_db)
    assert new_position in used and recent["processed"] == 1
    assert (
        fresh_db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE position_id=?", (new_position,)
        ).fetchone()[0]
        == new_runs + 1
    )

    # An unavailable newest decision advances and wraps, even after reopening.
    import chess_coach.material_recent_observe as fresh_observe

    real_process = fresh_observe.process_item

    def unavailable(target, position, subject, report, outcomes):
        if position == new_position:
            report["unavailable"] += 1
            return None
        return real_process(target, position, subject, report, outcomes)

    state = fresh_state(fresh_db, LEARNER)
    save_fresh_state(
        fresh_db,
        LEARNER,
        {**state, "positions": [item for item in state["positions"] if item[0] != 3]},
    )
    with monkeypatch.context() as patch:
        patch.setattr(fresh_observe, "process_item", unavailable)
        used, report, _recent = tick(fresh_db)
        assert new_position in used and report["unavailable"] == 1
        fresh_db.close()
        fresh_db = Database(fresh_path)
        used, _report, recent = tick(fresh_db)
        assert new_position not in used and recent["replayed"] == 1
    tick(fresh_db)
    used, _report, recent = tick(fresh_db)
    assert new_position not in used and recent["processed"] == 1
    tick(fresh_db)
    tick(fresh_db)
    used, _report, recent = tick(fresh_db)
    assert new_position in used and recent["replayed"] == 1
    # A previously imported older game is prioritized when analysis completes.
    add_fixture_game(fresh_db, "Already imported", 1)
    _used, _report, recent = tick(fresh_db)
    assert recent["source_unavailable"] >= 1
    run_analysis(fresh_db, 4, game_input(fresh_db, 4), minimal, engine_identity(sys.executable))
    older_position = fresh_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=4 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    used, _report, recent = tick(fresh_db)
    assert older_position in used and recent["processed"] == 1
    fresh_db.close()

    duplicate_db = make_game(tmp_path / "duplicate-material.sqlite", monkeypatch)
    duplicate = process_material(duplicate_db, recent_config)
    assert duplicate["recent"]["processed"] == 1
    assert duplicate["processed"] == 1 and duplicate["replayed"] == 0
    assert duplicate["examined"] == 3
    assert (
        duplicate_db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE status='active' AND producer=?",
            ("material-opportunity",),
        ).fetchone()[0]
        == 1
    )

    import chess_coach.material_recent_observe as recent_observe

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    for scan_limit, decision_limit in ((1, 1), (1, 2), (4, 1)):
        single_db = make_game(
            tmp_path / f"single-material-{scan_limit}-{decision_limit}.sqlite", monkeypatch
        )
        add_fixture_game(single_db, "Second", 2)
        add_fixture_game(single_db, "Third", 3)
        one = PipelineConfig(
            learner=LEARNER,
            engine_path=sys.executable,
            nodes=100,
            material_max_scan=scan_limit,
            material_max_decisions=decision_limit,
        )
        for game_id in (2, 3):
            assert (
                run_analysis(
                    single_db,
                    game_id,
                    game_input(single_db, game_id),
                    one,
                    engine_identity(sys.executable),
                )["status"]
                == "complete"
            )
        first = process_material(single_db, one)
        assert first["processed"] == 1 and first["recent"]["pending"] is None
        assert first["recent"]["status"] == "not_scanned"
        with monkeypatch.context() as patch:
            patch.setattr(recent_observe, "process_item", interrupt)
            with pytest.raises(KeyboardInterrupt):
                process_material(single_db, one)
        _key, positions = archive_scan(single_db, LEARNER, 1)
        assert positions[0]["id"] == 2
        after_interrupt = process_material(single_db, one)
        assert after_interrupt["recent"]["pending"] is None
        assert after_interrupt["examined"] <= scan_limit
        _key, positions = archive_scan(single_db, LEARNER, 1)
        expected_next = 3 if scan_limit == 1 else 4
        assert positions[0]["id"] == expected_next
        next_recent = process_material(single_db, one)
        assert next_recent["recent"]["processed"] == 1
        assert next_recent["recent"]["game_window"] == 10
        assert next_recent["recent"]["observed"] == 1
        assert next_recent["examined"] <= scan_limit and next_recent["processed"] <= decision_limit
        _key, positions = archive_scan(single_db, LEARNER, 1)
        assert positions[0]["id"] == expected_next


@pytest.mark.skipif(
    not __import__("pathlib").Path("/usr/games/stockfish").is_file(),
    reason="Stockfish not installed",
)
def test_real_stockfish_bounded_worker_records_nonmate_observation(tmp_path):
    import httpx

    from chess_coach.pipeline import process_pipeline

    board = chess.Board("4k3/7p/8/8/3q4/8/P7/3RK3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_uci("e1f1"))
    board.push_uci("e1f1")
    node.add_variation(board.parse_uci("e8f8"))
    db = Database(tmp_path / "real.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    config = PipelineConfig(
        learner=LEARNER,
        engine_path="/usr/games/stockfish",
        nodes=10000,
        seconds_per_position=1.0,
        deep_enabled=False,
        material_max_decisions=1,
    )
    result = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    )
    assert result["material"]["processed"] == 1
    row = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE fact_type=?", ("material_opportunity",)
    ).fetchone()
    assert row is not None
    import json

    observation = json.loads(row["payload_json"])
    assert observation["kind"] in {"material_capture", "material_protection"}
    assert observation["outcome"] in {"success", "failure", "ambiguous"}


def make_protection_game(path, monkeypatch, *, timed=True, played="a2a3", color="white"):
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")

    def orient(uci):
        move = chess.Move.from_uci(uci)
        if color == "black":
            move = chess.Move(
                chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
            )
        return move.uci()

    if color == "black":
        board = board.mirror()
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER if color == "white" else "fixture_opponent"
    game.headers["Black"] = LEARNER if color == "black" else "fixture_opponent"
    game.headers["Result"] = "*"
    if timed:
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(orient(played)))
    board.push_uci(orient(played))
    reply = "c5d4" if played == "a2a3" else "e8f8"
    node.add_variation(board.parse_uci(orient(reply)))

    class ProtectionEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if board.move_stack:
                return [
                    {
                        "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                        "pv": [root_moves[0] if root_moves else next(iter(board.legal_moves))],
                        "nodes": 100,
                        "depth": 5,
                    }
                ]
            move = root_moves[0] if root_moves else chess.Move.from_uci(orient("d4d5"))
            reply = chess.Move.from_uci(orient("c5d4" if move.uci() == orient("a2a3") else "e8f8"))
            score = 0 if root_moves else 500
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                    "pv": [move, reply],
                    "nodes": 100,
                    "depth": 5,
                }
            ]

    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: ProtectionEngine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    result = run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    return db
