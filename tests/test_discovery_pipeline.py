"""Integrated synthetic discovery worker, ownership, review, and practice."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.discovery_pipeline import process_discoveries
from chess_coach.discovery_practice import VERSION, list_candidates
from chess_coach.discovery_practice_source import resolve
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.lesson_narrative import build
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.recurrence_report import report
from chess_coach.unified_session_events import submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app

LEARNER = "fixture_learner"


class Engine:
    def __init__(self):
        self.id = {"name": "synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        if not board.move_stack:
            move = root_moves[0] if root_moves else chess.Move.from_uci("h6f7")
        else:
            move = root_moves[0] if root_moves else next(iter(board.legal_moves))
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(100), board.turn),
                "pv": [move],
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def make_game(path, monkeypatch):
    board = chess.Board("7k/8/5K1N/8/8/8/8/6RR w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": LEARNER,
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("g1f1"))
    board.push_uci("g1f1")
    node.add_variation(board.parse_uci("h8h7"))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    return db, config


def test_source_worker_lesson_practice_and_review(tmp_path, monkeypatch):
    path = tmp_path / "discovery.sqlite"
    db, config = make_game(path, monkeypatch)
    worker = process_discoveries(db, config)
    assert worker["outcomes"]["failure"] == 1
    evidence_id = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("discovered_attack",)
    ).fetchone()[0]
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["discovery_currentness"] == "current"
    assert evidence["discovery_observation"]["proof"]["double_check"]
    assert process_discoveries(db, config)["replayed"] >= 1
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, LEARNER, "discovered_attack", "execute", datetime.now(UTC)
    )
    assert not eligible and excluded["discovery_family_unvalidated"] == 1
    result = report(
        db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="execute",
    )
    lesson = build(db, LEARNER, result["current"][0])
    assert any("double check" in text for text in lesson["examples"][0]["facts"])
    assert list_candidates(db, LEARNER)["candidates"][0]["key"] == str(evidence_id)
    assert resolve(db, VERSION, str(evidence_id), LEARNER)["lines"] == ["h6f7"]
    start(
        db,
        attempt_id="fixture_attempt",
        subject=LEARNER,
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    assert (
        submit(db, "fixture_attempt", LEARNER, event_id="move-1", move="h6f7")["status"]
        == "objective_verified"
    )
    with pytest.raises(ValueError):
        resolve(db, VERSION, str(evidence_id), "fixture_other")
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Discovered-attack source: current" in page.data and b"double check" in page.data
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["discovery_currentness"] == "stale"
    with pytest.raises(ValueError):
        resolve(db, VERSION, str(evidence_id), LEARNER)

    # A missed immediate discovered mate is a separate prevent source.
    from chess_coach.discovery_defense_contract import PRACTICE
    from chess_coach.discovery_defense_observation import observe as observe_defense
    from chess_coach.discovery_defense_pipeline import process_defenses
    from chess_coach.discovery_defense_practice import resolve as resolve_defense
    from tests.test_fork_defense_pipeline import Engine as DefenseEngine

    board = chess.Board("5n1k/p7/5K1N/8/8/8/8/6RR b - - 0 1")

    def source_line(moves):
        return {
            "root_move": moves.split()[0],
            "pv": moves,
            "status": "limited",
            "score_bound": "exact",
        }

    actual, best, mate = "a7a6", "f8g6", "h6f7"
    outcome = observe_defense(board, actual, source_line(best), source_line(actual + " " + mate))
    assert outcome["outcome"] == "failure" and outcome["threat"]["double_check"]
    assert outcome["witness"]["move"] not in {actual, best}
    checking = "f8h7"
    assert board.gives_check(board.parse_uci(checking))
    assert (
        observe_defense(board, actual, source_line(checking), source_line(actual + " " + mate))[
            "outcome"
        ]
        == "failure"
    )
    mirrored = board.mirror()

    def mirror(text):
        move = chess.Move.from_uci(text)
        return chess.Move(
            chess.square_mirror(move.from_square),
            chess.square_mirror(move.to_square),
            promotion=move.promotion,
        ).uci()

    reversed_result = observe_defense(
        mirrored,
        mirror(actual),
        source_line(mirror(best)),
        source_line(mirror(actual) + " " + mirror(mate)),
    )
    assert reversed_result["outcome"] == "failure" and reversed_result["threat"]["mate"]
    assert observe_defense(board, "a7a5", source_line(best), source_line("a7a5 " + mate)) is None

    defense_path = tmp_path / "discovery-defense.sqlite"
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_opponent",
            "Black": LEARNER,
            "Result": "1-0",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:01:00",
        }
    )
    first = game.add_variation(board.parse_uci(actual))
    board.push_uci(actual)
    first.add_variation(board.parse_uci(mate))
    defense_db = Database(defense_path)
    defense_db.initialize()
    ingest_pgn(defense_db, str(game))
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _: DefenseEngine([best], [actual, mate])
    )
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(
            defense_db, 1, game_input(defense_db, 1), config, engine_identity(sys.executable)
        )["status"]
        == "complete"
    )
    worker = process_defenses(defense_db, config)
    assert worker["limits"] == {"positions": 20, "decisions": 4}
    assert worker["outcomes"]["failure"] == 1
    defense_id = defense_db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?",
        ("discovered_attack", "prevent"),
    ).fetchone()[0]
    source = inspect_evidence(defense_db, defense_id)
    assert source["discovery_defense_currentness"] == "current"
    assert process_defenses(defense_db, config)["replayed"] >= 1
    review_evidence(defense_db, defense_id, decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        defense_db, LEARNER, "discovered_attack", "prevent", datetime.now(UTC)
    )
    assert not eligible and excluded["discovery_family_unvalidated"] == 1
    grouped = report(
        defense_db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="prevent",
    )
    teaching = build(defense_db, LEARNER, grouped["current"][0])
    assert any("prevents every immediate" in fact for fact in teaching["examples"][0]["facts"])
    snap = resolve_defense(defense_db, PRACTICE, str(defense_id), LEARNER)
    assert snap["learner_color"] == "black" and snap["objective"] == "avoid_immediate_mate"
    assert snap["lines"] == [best]
    start(
        defense_db,
        attempt_id="defense",
        subject=LEARNER,
        source_type="own-game",
        version=PRACTICE,
        key=str(defense_id),
    )
    assert (
        submit(defense_db, "defense", LEARNER, event_id="answer", move=best)["status"]
        == "objective_verified"
    )
    with pytest.raises(ValueError):
        resolve_defense(defense_db, PRACTICE, str(defense_id), "fixture_other")
    start(
        defense_db,
        attempt_id="other-defense",
        subject=LEARNER,
        source_type="own-game",
        version=PRACTICE,
        key=str(defense_id),
    )
    assert (
        submit(defense_db, "other-defense", LEARNER, event_id="check", move=checking)["status"]
        == "needs_verification"
    )
    from chess_coach.objective_status import inspect as inspect_objective
    from chess_coach.objective_worker import process as process_objectives

    assert process_objectives(defense_db, LEARNER)["outcomes"] == {"correct": 1}
    assert inspect_objective(defense_db, LEARNER, "other-defense", "check")["status"] == "correct"
    start(
        defense_db,
        attempt_id="pending-defense",
        subject=LEARNER,
        source_type="own-game",
        version=PRACTICE,
        key=str(defense_id),
    )
    defense_app = create_app(
        db_path=defense_path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    before_get = defense_db.connection.total_changes
    page = defense_app.test_client().get(
        f"/evidence/{defense_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Discovered-mate defense source is current" in page.data
    assert b"independently tested legal alternative" in page.data
    assert defense_db.connection.total_changes == before_get
    review_evidence(defense_db, defense_id, decision="revoke", actor="fixture_reviewer")
    from chess_coach.unified_session_events import show

    with pytest.raises(ValueError):
        show(defense_db, "pending-defense", LEARNER)
    with pytest.raises(ValueError):
        resolve_defense(defense_db, PRACTICE, str(defense_id), LEARNER)
    review_evidence(defense_db, defense_id, decision="accept", actor="fixture_reviewer")
    defense_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    defense_db.connection.commit()
    assert inspect_evidence(defense_db, defense_id)["discovery_defense_currentness"] == "stale"
    with pytest.raises(ValueError):
        resolve_defense(defense_db, PRACTICE, str(defense_id), LEARNER)

    # Material prevention uses the same bounded scan and a separate replay objective.
    from chess_coach.discovery_material_contract import MAPPER as MATERIAL_MAPPER
    from chess_coach.discovery_material_contract import PRACTICE as MATERIAL_PRACTICE
    from chess_coach.discovery_material_observation import observe as observe_material
    from chess_coach.discovery_material_practice import resolve as resolve_material
    from chess_coach.unified_session_events import show as show_session

    material_board = chess.Board("8/Q2K4/8/8/n7/7P/1P5k/r7 w - - 0 1")
    played_moves = ["a7a8", "a4b6", "d7e7", "a1a8"]
    best_moves = ["a7c5", "a4b6", "d7e7", "h2h1"]

    def scored(moves, score):
        return {**source_line(" ".join(moves)), "score_kind": "cp", "score_value": score}

    material = observe_material(
        material_board, played_moves[0], scored(best_moves, 200), scored(played_moves, 0)
    )
    assert material["outcome"] == "failure" and material["target_origin"] == "a7"
    assert material["threat"]["target"] == "a8" and material["threat"]["minimum_gain"] >= 3
    from chess_coach.fork_defense_comparison import failed as compare_defenses

    extended_best = ["a7c5", "a4b6", "d7e7", "b6c8", "e7f8", "c8e7"]
    compared, reason = compare_defenses(
        material_board,
        chess.Move.from_uci(played_moves[0]),
        chess.Move.from_uci(best_moves[0]),
        scored(played_moves, 0),
        scored(extended_best, 200),
        material["threat"],
    )
    assert reason is None and len(compared["played"]["uci"]) == 4
    assert len(compared["best"]["uci"]) == 6
    extended = observe_material(
        material_board, played_moves[0], scored(extended_best, 200), scored(played_moves, 0)
    )
    assert extended["outcome"] == "ambiguous"
    assert extended["reason"] == "comparison_horizon_unsupported"
    uncertain = observe_material(
        material_board, played_moves[0], scored(best_moves, 0), scored(played_moves, 0)
    )
    assert uncertain["outcome"] == "ambiguous"
    assert uncertain["reason"] == "engine_disagreement_or_compensation"

    material_path = tmp_path / "discovery-material.sqlite"
    material_game = chess.pgn.Game()
    material_game.setup(material_board)
    material_game.headers.update(
        {
            "White": LEARNER,
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:02:00",
        }
    )
    node = material_game
    for text in played_moves:
        move = material_board.parse_uci(text)
        node = node.add_variation(move)
        material_board.push(move)
    material_db = Database(material_path)
    material_db.initialize()
    ingest_pgn(material_db, str(material_game))
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _: DefenseEngine(best_moves, played_moves)
    )
    assert (
        run_analysis(
            material_db, 1, game_input(material_db, 1), config, engine_identity(sys.executable)
        )["status"]
        == "complete"
    )
    material_worker = process_defenses(material_db, config)
    assert material_worker["limits"] == {"positions": 20, "decisions": 4}
    material_id = material_db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
           WHERE r.producer=? AND e.position_id=1""",
        (MATERIAL_MAPPER,),
    ).fetchone()[0]
    material_evidence = inspect_evidence(material_db, material_id)
    assert material_evidence["discovery_material_currentness"] == "current"
    review_evidence(material_db, material_id, decision="accept", actor="fixture_reviewer")
    current = report(
        material_db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="prevent",
    )
    assert len(current["current"]) == 1 and current["current"][0]["family"] == MATERIAL_MAPPER
    material_lesson = build(material_db, LEARNER, current["current"][0])
    assert any(
        "origin" in fact and "unknown" in fact for fact in material_lesson["examples"][0]["facts"]
    )
    snapshot = resolve_material(material_db, MATERIAL_PRACTICE, str(material_id), LEARNER)
    assert snapshot["objective"] == "legal_line" and snapshot["lines"] == [best_moves[0]]
    start(
        material_db,
        attempt_id="material-defense",
        subject=LEARNER,
        source_type="own-game",
        version=MATERIAL_PRACTICE,
        key=str(material_id),
    )
    view = show_session(material_db, "material-defense", LEARNER)
    assert view["learner_color"] == "white" and view["discovery_target"] == "a7"
    assert (
        submit(material_db, "material-defense", LEARNER, event_id="move", move=best_moves[0])[
            "status"
        ]
        == "line_completed"
    )
    start(
        material_db,
        attempt_id="unlisted",
        subject=LEARNER,
        source_type="own-game",
        version=MATERIAL_PRACTICE,
        key=str(material_id),
    )
    assert (
        submit(material_db, "unlisted", LEARNER, event_id="move", move="a7a6")["status"]
        == "needs_verification"
    )
    assert (
        material_db.connection.execute(
            "SELECT COUNT(*) FROM objective_requests WHERE attempt_id=?", ("unlisted",)
        ).fetchone()[0]
        == 0
    )
    material_app = create_app(
        db_path=material_path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = material_app.test_client().get(
        f"/evidence/{material_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Discovered-material defense source is current" in page.data
    assert b"origin of the threat" in page.data
    replay_page = material_app.test_client().get(
        "/unified/unlisted",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Other legal defenses remain ungraded" in replay_page.data
    assert b"This legal move is ungraded" in replay_page.data
    assert b"Status: Ungraded" in replay_page.data
    assert b"Replay a defense to the named discovered attack" in replay_page.data
    review_evidence(material_db, material_id, decision="revoke", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        resolve_material(material_db, MATERIAL_PRACTICE, str(material_id), LEARNER)
    review_evidence(material_db, material_id, decision="accept", actor="fixture_reviewer")
    material_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=0 WHERE position_id=1 AND role=?",
        ("best",),
    )
    material_db.connection.commit()
    assert inspect_evidence(material_db, material_id)["discovery_material_currentness"] == "stale"
    with pytest.raises(ValueError):
        resolve_material(material_db, MATERIAL_PRACTICE, str(material_id), LEARNER)
    unresolved_worker = process_defenses(material_db, config)
    assert unresolved_worker["material_unresolved"]["engine_disagreement_or_compensation"] >= 1
    from collections import Counter

    from chess_coach.discovery_prevent_worker_item import combined

    unresolved_counts = Counter()
    rechecked = combined(material_db, 1, LEARNER, exclusions=unresolved_counts)
    assert not rechecked["replayed"]
    assert unresolved_counts["engine_disagreement_or_compensation"] == 1
    import chess_coach.discovery_material_pipeline as material_pipeline
    import chess_coach.discovery_prevent_worker_item as prevent_worker

    with monkeypatch.context() as patch:
        patch.setattr(
            prevent_worker,
            "mate_source",
            lambda *_args, **_kw: {
                "outcome": "ambiguous",
                "replayed": False,
            },
        )
        patch.setattr(
            material_pipeline,
            "process_source",
            lambda *_args: {
                "outcome": "failure",
                "replayed": True,
            },
        )
        assert not combined(material_db, 1, LEARNER, exclusions=Counter())["replayed"]

    # Material success proves a distinct witness and follows the same target.
    from chess_coach.discovery_material_success_contract import MAPPER as MATERIAL_SUCCESS_MAPPER
    from chess_coach.discovery_material_success_observation import observe as material_success

    position = chess.Board("8/Q2K4/8/8/n7/7P/1P5k/r7 w - - 0 1")
    proved = material_success(position, "a7b7")
    assert proved["outcome"] == "success"
    assert proved["witness"]["move"] == "a7a8"
    assert proved["target_origin"] == "a7" and proved["threat"]["legal_replies"] == 7
    assert material_success(position, "a7c5")["reason"] == "played_target_or_line_unresolved"

    safe_game = chess.pgn.Game()
    safe_game.setup(position)
    safe_game.headers.update(
        {
            "White": LEARNER,
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:02:30",
        }
    )
    safe_game.add_variation(position.parse_uci("a7b7"))
    ingest_pgn(material_db, str(safe_game))
    game_id = material_db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    position_id = material_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=1", (game_id,)
    ).fetchone()[0]
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _: DefenseEngine(["a7b7"], ["a7b7"])
    )
    assert (
        run_analysis(
            material_db,
            game_id,
            game_input(material_db, game_id),
            config,
            engine_identity(sys.executable),
        )["status"]
        == "complete"
    )
    result = combined(material_db, position_id, LEARNER, exclusions=Counter(), successes=Counter())
    assert result["outcome"] == "success"
    material_success_id = material_db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
           WHERE r.producer=? AND e.position_id=?""",
        (MATERIAL_SUCCESS_MAPPER, position_id),
    ).fetchone()[0]
    assert (
        inspect_evidence(material_db, material_success_id)["discovery_material_success_currentness"]
        == "current"
    )
    review_evidence(material_db, material_success_id, decision="accept", actor="fixture_reviewer")
    groups = report(
        material_db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="prevent",
    )
    group = next(item for item in groups["current"] if item["family"] == MATERIAL_SUCCESS_MAPPER)
    assert group["successes"] == 1
    lesson = build(material_db, LEARNER, group)
    assert any(
        "distinct legal alternative" in fact.lower() for fact in lesson["examples"][0]["facts"]
    )
    branch = proved["threat"]["branches"][0]
    expected_line = [
        proved["witness"]["san"],
        proved["threat"]["san"],
        branch["reply_san"],
        branch["capture_san"],
    ]
    assert any(line["moves"] == expected_line for line in lesson["examples"][0]["lines"])
    page = material_app.test_client().get(
        f"/evidence/{material_success_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert " ".join(expected_line).encode() in page.data
    assert b"gain of at least 3 pawn units" in page.data
    material_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=? AND role=?",
        (position_id, "best"),
    )
    material_db.connection.commit()
    assert (
        inspect_evidence(material_db, material_success_id)["discovery_material_success_currentness"]
        == "stale"
    )

    # Success uses an independent witness even when best and played roots match.
    import time

    from chess_coach.discovery_mate_success_contract import MAPPER as SUCCESS_MAPPER
    from chess_coach.discovery_mate_success_observation import observe as observe_success
    from chess_coach.discovery_mate_success_source import process_source as success_source
    from chess_coach.material_source import prepare

    success_board = chess.Board("5n1k/p7/5K1N/8/8/8/8/6RR b - - 0 1")
    safe_move = "f8g6"
    success = observe_success(success_board, safe_move)
    assert success["outcome"] == "success" and success["threat"]["double_check"]
    assert success["witness"]["move"] != safe_move
    timed_out = observe_success(success_board, safe_move, started=time.monotonic() - 2)
    assert timed_out["reason"] == "proof_deadline_exhausted"
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.discovery_mate_success_probe.MAX_CANDIDATES", 0)
        limited = observe_success(success_board, safe_move)
        assert limited["reason"] == "nomination_limit_or_unavailable"
    assert all(
        success["witness"]["nomination"][key] == success["threat"][key]
        for key in ("move", "slider", "moved_from", "moved_to", "target")
    )
    reverse = observe_success(success_board.mirror(), mirror(safe_move))
    assert reverse["outcome"] == "success"
    repeated = chess.Board("7k/p3n3/5K1N/8/8/8/8/6RR b - - 0 1")
    for move in ("e7g6", "g1f1", "g6f8", "f1g1"):
        repeated.push_uci(move)
    endpoint = repeated.copy()
    endpoint.push_uci(safe_move)
    assert not repeated.is_repetition(2)
    assert endpoint.is_repetition(2) and not endpoint.is_game_over(claim_draw=True)
    repeated_result = observe_success(repeated, safe_move)
    assert repeated_result["outcome"] == "ambiguous"
    assert repeated_result["reason"] == "played_repeated_or_terminal"
    unknown_board = chess.Board("5n1k/p7/5K1N/8/8/8/8/6RR b - - 8 1")
    assert observe_success(unknown_board, safe_move)["reason"] == (
        "history_or_position_unavailable"
    )

    success_path = tmp_path / "discovery-success.sqlite"
    success_game = chess.pgn.Game()
    success_game.setup(success_board)
    success_game.headers.update(
        {
            "White": "fixture_opponent",
            "Black": LEARNER,
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:03:00",
        }
    )
    first = success_game.add_variation(success_board.parse_uci(safe_move))
    success_board.push_uci(safe_move)
    first.add_variation(success_board.parse_uci("h6f7"))
    success_db = Database(success_path)
    success_db.initialize()
    ingest_pgn(success_db, str(success_game))
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda _: DefenseEngine([safe_move, "h6f7"], [safe_move, "h6f7"]),
    )
    assert (
        run_analysis(
            success_db, 1, game_input(success_db, 1), config, engine_identity(sys.executable)
        )["status"]
        == "complete"
    )
    successes = process_defenses(success_db, config)
    assert successes["limits"] == {"positions": 20, "decisions": 4}
    assert successes["outcomes"]["success"] == 1
    success_id = success_db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
           WHERE r.producer=? AND e.position_id=1""",
        (SUCCESS_MAPPER,),
    ).fetchone()[0]
    success_evidence = inspect_evidence(success_db, success_id)
    assert success_evidence["discovery_success_currentness"] == "current"
    prepared = prepare(success_db, 1, LEARNER)
    assert prepared["best"]["root_move"] == prepared["played"]["root_move"] == safe_move
    assert success_source(success_db, prepared, time.monotonic())["replayed"]
    review_evidence(success_db, success_id, decision="accept", actor="fixture_reviewer")
    success_eligible, success_excluded = eligible_contexts(
        success_db, LEARNER, "discovered_attack", "prevent", datetime.now(UTC)
    )
    assert not success_eligible and success_excluded["discovery_family_unvalidated"] == 1
    success_groups = report(
        success_db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="prevent",
    )
    assert len(success_groups["current"]) == 1
    assert success_groups["current"][0]["successes"] == 1
    success_lesson = build(success_db, LEARNER, success_groups["current"][0])
    assert any(
        "distinct legal alternative" in fact.lower()
        for fact in success_lesson["examples"][0]["facts"]
    )
    success_app = create_app(
        db_path=success_path,
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    before_get = success_db.connection.total_changes
    page = success_app.test_client().get(
        f"/evidence/{success_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Discovered-mate success source is current" in page.data
    assert b"distinct legal quiet alternative" in page.data
    assert success_db.connection.total_changes == before_get
    review_evidence(success_db, success_id, decision="revoke", actor="fixture_reviewer")
    hidden = report(
        success_db,
        LEARNER,
        "2025-12-31T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
        skill="discovered_attack",
        operation="prevent",
    )
    assert not hidden["current"]
    review_evidence(success_db, success_id, decision="accept", actor="fixture_reviewer")
    success_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    success_db.connection.commit()
    assert inspect_evidence(success_db, success_id)["discovery_success_currentness"] == "stale"
