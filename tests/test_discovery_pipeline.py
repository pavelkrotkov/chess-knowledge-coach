"""Integrated synthetic discovery worker, ownership, review, and practice."""

import json
import re
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
    _recorded_public_material_workflow(tmp_path, monkeypatch)
    _recent_defense_workflow(monkeypatch)
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
    client = app.test_client()
    page = client.get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert b"Discovered-attack source: current" in page.data and b"double check" in page.data
    assert b"Find unfamiliar discovered-mate practice" in page.data

    # A different legal reset position shares the source's discovered-mate roles.
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','hash','staging')"
    )
    corpus_id = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version='test'"
    ).fetchone()[0]
    for file in "abcd":
        candidate = chess.Board("7k/8/5K1N/8/8/8/8/6RR b - - 0 1")
        candidate.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        setup = file + "7" + file + "6"
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,?,?,1200,80,'[]','unknown')""",
            (
                file,
                corpus_id,
                candidate.fen(),
                "https://lichess.org/external" + file,
                setup + " h6f7",
            ),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'discoveredAttack',1200)", (corpus_id, file)
        )
    wrong_check = chess.Board("7k/8/5K1N/8/8/8/8/6RR b - - 0 1")
    wrong_check.set_piece_at(chess.D7, chess.Piece(chess.PAWN, chess.BLACK))
    no_reset = chess.Board("1n5k/8/5K1N/8/8/8/8/6RR b - - 0 1")
    for key, board, line in (
        ("wrong-check", wrong_check, "d7d6 h6g8"),
        ("no-reset", no_reset, "b8a6 h6f7"),
    ):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (key, corpus_id, board.fen(), line),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'discoveredAttack',1200)", (corpus_id, key)
        )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus_id,))
    db.connection.commit()
    headers = {"Tailscale-User-Login": "fixture-login"}
    origin = "https://coach.invalid"
    url = f"/evidence/{evidence_id}/related-discovered-mates"
    from chess_coach.unified_session_events import hint, reveal, show

    for index, (move, expected) in enumerate(
        (
            ("h6f5", "objective_verified"),
            ("g1f1", "line_completed"),
            (None, "imported"),
            (None, "revoked"),
        )
    ):
        preview = client.get(url, base_url=origin, headers=headers)
        assert preview.status_code == 200
        assert preview.data.count(b"Try this assessment") == 4 - index
        assert b"h6f7" not in preview.data and b"Play White" in preview.data
        match = re.search(rb'name="reference" value="([0-9a-f]{64})"', preview.data)
        assert match is not None
        reference = match.group(1).decode()
        with client.session_transaction(base_url=origin) as browser:
            csrf = browser["csrf"]
        started = client.post(
            url + "/start",
            base_url=origin,
            headers=headers | {"Origin": origin},
            data={"csrf": csrf, "reference": reference},
        )
        assert started.status_code == 303
        with client.session_transaction(base_url=origin) as browser:
            attempt = browser["unified_attempt"]
        active = client.get(started.headers["Location"], base_url=origin, headers=headers)
        assert b"h6f7" not in active.data and b">Hint</button>" not in active.data
        with pytest.raises(ValueError, match="answer before"):
            hint(db, attempt, LEARNER, event_id="hint")
        with pytest.raises(ValueError, match="answer before"):
            reveal(db, attempt, LEARNER, event_id="reveal")
        if expected == "imported":
            stored = db.connection.execute(
                "SELECT provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
            source_game = json.loads(stored)["related_discovery_mate"]["source_game"]
            game = chess.pgn.Game()
            game.headers.update(
                {
                    "White": LEARNER,
                    "Black": "fixture_opponent",
                    "Result": "1-0",
                    "Site": "https://lichess.org/" + source_game,
                }
            )
            game.add_variation(chess.Move.from_uci("e2e4"))
            ingest_pgn(db, str(game), source="lichess")
            with pytest.raises(ValueError):
                submit(db, attempt, LEARNER, event_id="answer", move="h6f7")
        elif move is None:
            review_evidence(db, evidence_id, decision="revoke", actor="fixture_reviewer")
            with pytest.raises(ValueError):
                submit(db, attempt, LEARNER, event_id="answer", move="h6f7")
            review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
        else:
            answer = submit(db, attempt, LEARNER, event_id="answer", move=move)
            assert answer["status"] == expected and answer["hints_used"] == 0
            assert answer["feedback"] == (
                "objective_verified" if expected == "objective_verified" else "incorrect"
            )
            assert show(db, attempt, LEARNER)["status"] == expected
            result_page = client.get(started.headers["Location"], base_url=origin, headers=headers)
            if expected == "objective_verified":
                assert b"gave checkmate without assistance" in result_page.data
            else:
                assert b"Incorrect: this legal move did not give checkmate" in result_page.data

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
    material_client = material_app.test_client()
    origin = "https://coach.invalid"
    headers = {"Tailscale-User-Login": "fixture-login"}
    dates = {
        "compare_start": "2025-12-01T00:00:00+00:00",
        "start": "2025-12-31T00:00:00+00:00",
        "end": "2026-02-01T00:00:00+00:00",
        "skill": "discovered_attack",
        "operation": "prevent",
    }
    recurrence = material_client.get(
        "/recurrence", query_string=dates, base_url=origin, headers=headers
    )
    assert recurrence.status_code == 200
    assert b"Replay this material defense" in recurrence.data
    assert (
        b"cued recorded-line rehearsal" in recurrence.data
        and b"Other legal defenses remain ungraded" in recurrence.data
    )
    assert MATERIAL_PRACTICE.encode() in recurrence.data
    from chess_coach import lesson_discovery_material_rehearsal

    with monkeypatch.context() as patch:
        patch.setattr(
            lesson_discovery_material_rehearsal,
            "resolve",
            lambda *_: (_ for _ in ()).throw(ValueError("preflight unavailable")),
        )
        unavailable = material_client.get(
            "/recurrence", query_string=dates, base_url=origin, headers=headers
        )
        assert b"Replay this material defense" not in unavailable.data
        assert b"other material threats" in unavailable.data
    with material_client.session_transaction(base_url=origin) as session:
        csrf = session["csrf"]
    post_headers = headers | {"Origin": origin}
    form = {
        "csrf": csrf,
        "source_type": "own-game",
        "version": MATERIAL_PRACTICE,
        "key": str(material_id),
    }
    before_learning = [
        material_db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in ("training_attempts", "mastery_events", "objective_requests")
    ]
    started = material_client.post(
        "/unified/start", base_url=origin, headers=post_headers, data=form
    )
    assert started.status_code == 303
    active = material_client.get(started.headers["Location"], base_url=origin, headers=headers)
    assert b"Replay a defense to the named discovered attack" in active.data
    assert [
        material_db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in ("training_attempts", "mastery_events", "objective_requests")
    ] == before_learning
    material_app.config["SUBJECT"] = "fixture_other"
    foreign = material_client.get(
        "/recurrence", query_string=dates, base_url=origin, headers=headers
    )
    assert b"Replay this material defense" not in foreign.data
    assert (
        material_client.post(
            "/unified/start", base_url=origin, headers=post_headers, data=form
        ).status_code
        == 400
    )
    material_app.config["SUBJECT"] = LEARNER

    from chess_coach.lesson_discovery_material_rehearsal import attach
    from chess_coach.lesson_history import save

    attach(material_db, LEARNER, material_lesson)
    assert material_lesson["examples"][0]["discovery_material_rehearsal"]
    saved_id = save(material_db, LEARNER, material_lesson)
    material_db.connection.commit()
    saved = material_client.get(f"/lessons/{saved_id}", base_url=origin, headers=headers)
    assert (
        b"historical snapshot" in saved.data and b"Replay this material defense" not in saved.data
    )

    page = material_client.get(
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
    revoked_page = material_client.get(
        "/recurrence", query_string=dates, base_url=origin, headers=headers
    )
    assert b"Replay this material defense" not in revoked_page.data
    assert (
        material_client.post(
            "/unified/start", base_url=origin, headers=post_headers, data=form
        ).status_code
        == 400
    )
    with pytest.raises(ValueError):
        resolve_material(material_db, MATERIAL_PRACTICE, str(material_id), LEARNER)
    review_evidence(material_db, material_id, decision="accept", actor="fixture_reviewer")
    material_db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=0 WHERE position_id=1 AND role=?",
        ("best",),
    )
    material_db.connection.commit()
    assert inspect_evidence(material_db, material_id)["discovery_material_currentness"] == "stale"
    stale_page = material_client.get(
        "/recurrence", query_string=dates, base_url=origin, headers=headers
    )
    assert b"Replay this material defense" not in stale_page.data
    assert (
        material_client.post(
            "/unified/start", base_url=origin, headers=post_headers, data=form
        ).status_code
        == 400
    )
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


def _recorded_public_material_workflow(tmp_path, monkeypatch):
    """Exercise the isolated public recorded-discovery profile on original histories."""
    import base64
    import contextlib
    import hashlib
    import io
    import random
    import sqlite3
    import subprocess
    import time

    import httpx

    import chess_coach.mastery as mastery
    import chess_coach.objective_worker as objective_worker
    import chess_coach.opening_public_discovery_material_example as material_example
    import chess_coach.opening_public_discovery_material_game as material_game
    import chess_coach.ops_opening_profile as profile_cli
    from chess_coach.fact_fingerprint import canonical, digest
    from chess_coach.objective_short_history import history_hash
    from chess_coach.opening_classification import classify_game
    from chess_coach.opening_full_history_build import build as build_history
    from chess_coach.opening_profile_cli_db import private_database
    from chess_coach.opening_public_discovery_material_policy import policy
    from chess_coach.opening_public_fork_later import bound
    from chess_coach.opening_public_proof_coverage import _selected
    from chess_coach.opening_public_proof_source import binding
    from chess_coach.opening_recent_acquire import acquire
    from chess_coach.opening_recent_index import build as build_recent
    from chess_coach.opening_recent_source import PREFIX_BYTES, PREFIX_NAME
    from chess_coach.opening_snapshot import SOURCE, VERSION, import_snapshot
    from chess_coach.style_schedule_budget import history_budget

    tail = "Bc4 Bc5 O-O d6 d3 Nf6 c3 Nd4 Nh4 O-O Bb5 a6 f4 a5 Qe2 Ng4 Qf2 h6 Re1"
    lines = (f"e4 e5 Nf3 Nc6 {tail} Nf3+", f"e4 Nc6 Nf3 e5 {tail} Nf3+")
    games = []
    for index, line in enumerate(lines):
        board = chess.Board()
        for san in line.split():
            board.push_san(san)
        assert len(board.move_stack) == 24
        game = chess.pgn.Game.from_board(board)
        game.headers.update(
            Event="Rated Blitz game",
            White=f"Peer {index}-{1100 + index}",
            Black=f"Reference {index}-{1200 + index}",
            Result="0-1",
            Date="2026.10.01",
            TimeControl="600+0",
            WhiteElo="1650",
            BlackElo="1700",
        )
        games.append((game, [move.uci() for move in board.move_stack]))
    board = chess.Board()
    for uci in games[0][1][:23]:
        board.push_uci(uci)
    assert chess.Move.from_uci("h6h5") in board.legal_moves
    board.push_uci("h6h5")
    variant = chess.pgn.Game.from_board(board)
    variant.headers.update(
        Event="Rated Blitz game",
        White="Peer 2-1102",
        Black="Reference 2-1202",
        Result="0-1",
        Date="2026.10.01",
        TimeControl="600+0",
        WhiteElo="1650",
        BlackElo="1700",
    )
    variant_moves = [move.uci() for move in board.move_stack]
    root = tmp_path / "public-discovery-material"
    planning, data = root / ".runtime" / "planning", root / ".runtime" / "data"
    planning.mkdir(parents=True, mode=0o700)
    data.mkdir(mode=0o700)
    db_path = data / "synthetic.sqlite"
    with monkeypatch.context() as patch:
        patch.delenv("CHESS_SCHEMA_COMPAT", raising=False)
        db = Database(db_path)
        db.initialize()
        import_snapshot(db)
        owned = games[0][0]
        owned.headers.update(
            White="synthetic peer", Black="learner", UTCDate="2026.01.02", UTCTime="12:06:00"
        )
        ingest_pgn(db, str(owned))
        game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
        position_id = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=2", (game_id,)
        ).fetchone()[0]
        classify_game(db, game_id, version=VERSION, source_url=SOURCE)
        db.close()
        before = hashlib.sha256(db_path.read_bytes()).hexdigest()
        owned.headers.update(White="Peer 0-1100", Black="Reference 0-1200")
        text = "\n\n".join([*(str(game) for game, _ in games), str(variant)])
        noise = base64.b64encode(random.Random(795).randbytes(1_400_000)).decode()
        compressed = subprocess.run(
            ["/usr/bin/zstd", "-q", "-c"],
            input=(text + "\n\n{" + noise).encode(),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        assert len(compressed) > PREFIX_BYTES
        prefix = compressed[:PREFIX_BYTES]

        def response(request):
            return httpx.Response(
                206,
                headers={
                    "Content-Range": f"bytes 0-{PREFIX_BYTES - 1}/{PREFIX_BYTES * 2}",
                    "Content-Length": str(PREFIX_BYTES),
                    "ETag": '"synthetic-discovery"',
                },
                content=prefix,
                request=request,
            )

        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            acquire(root, "learner", client=client)
        assert build_recent(root, "learner")["accepted"] == 3
        assert build_history(root, "learner")["accepted"] == 3
        deadline = time.monotonic() + 30
        with private_database(root, "learner", database=db_path) as read_db:
            with history_budget(deadline=deadline):
                base, _ = binding(read_db, root, "learner", game_id, position_id, "b8c6", deadline)
            full = bound(root, "learner", deadline)
        assert base["reference"]["license"] == "CC0-1.0"
        assert base["reference"]["source_sha256"] == hashlib.sha256(prefix).hexdigest()
        selected = policy(base, full[1], "initial")
        selected = {**selected, "index_sha256": full[1]}
        with sqlite3.connect(full[0][0].as_uri() + "?mode=ro&immutable=1", uri=True) as indexed:
            rows, _ = _selected(indexed, selected, base["source"]["played"], deadline)
            row = next(
                row
                for row in rows
                if json.loads(
                    indexed.execute(
                        "SELECT moves FROM histories WHERE game_id=?", (row[0],)
                    ).fetchone()[0]
                )
                == variant_moves
            )
            observed = material_game.inspect(
                indexed, row, selected, base["source"]["played"], deadline
            )
        assert observed["analyzed"] == 1 and observed["example"] is None

        patch.setenv("CHESS_DB", str(db_path))
        patch.setenv("CHESS_SUBJECT", "learner")
        args = [
            "opening-profile",
            "--project-root",
            str(root),
            "--game-id",
            str(game_id),
            "--position-id",
            str(position_id),
            "--alternative",
            "b8c6",
            "--reference",
            "recent",
        ]
        for window in ("continuation", "initial"):
            patch.setattr(
                sys,
                "argv",
                [
                    *args,
                    "--prepare-public",
                    "--proof-kind",
                    "discovery_material",
                    "--fork-window",
                    window,
                ],
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                profile_cli.main()
            prepared = json.loads(output.getvalue())
            assert prepared["discovery_material_policy"]["root_scope"] == "recorded"
            if window == "continuation":
                for branch in prepared["branches"].values():
                    assert branch["example"] is None and branch["preparation_incomplete"]
                continue
            for label, (_, moves) in zip(("played", "alternative"), games, strict=True):
                branch = prepared["branches"][label]
                assert branch["counts_scope"] == "completed_game_inspections"
                assert branch["unfinished_games"] == 0
                assert branch["supported"] == 1
                example = branch["example"]
                board = chess.Board()
                for uci in moves[:23]:
                    board.push_uci(uci)
                assert example["ply"] == 24 and example["recorded_uci"] == "d4f3"
                assert example["side_to_move"] == "black" and example["fen"] == board.fen()
                assert example["history_hash"] == history_hash(board)
                assert example["full_history_sha256"] == digest(canonical(moves))
                assert (
                    example["history_sha256"]
                    and example["record_hash"]
                    and example["source_identity"]
                )
                assert example["certificates"]
                for certificate in example["certificates"]:
                    assert (certificate["slider"], certificate["target"]) == ("c5", "f2")
                    assert (certificate["moved_from"], certificate["moved_to"]) == ("d4", "f3")
                    assert not certificate["mate"] and not certificate["double_check"]
                    assert certificate["minimum_gain"] >= 3 and certificate["legal_replies"] == 4
                    board.push_uci(example["recorded_uci"])
                    assert {b["reply"] for b in certificate["branches"]} == {
                        m.uci() for m in board.legal_moves
                    }
                    for witness in certificate["branches"]:
                        reply = chess.Move.from_uci(witness["reply"])
                        assert reply in board.legal_moves
                        following = board.copy(stack=True)
                        following.push(reply)
                        capture = chess.Move.from_uci(witness["capture"])
                        assert capture in following.legal_moves and capture.uci() == "c5f2"
                    board.pop()

        def forbidden(*_args, **_kwargs):
            pytest.fail("proof, engine, provider, or learning on private read")

        with patch.context() as read:
            read.setattr(material_example, "prove", forbidden)
            read.setattr(material_example, "discoveries", forbidden)
            read.setattr(chess.engine.SimpleEngine, "popen_uci", forbidden)
            read.setattr(httpx.Client, "send", forbidden)
            read.setattr(mastery, "update_mastery", forbidden)
            read.setattr(objective_worker, "process", forbidden)
            read.setattr(sys, "argv", [*args, "--proof-kind", "discovery_material"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                profile_cli.main()
            shown = json.loads(output.getvalue())["public_preparation"]
            assert shown["discovery_material_status"] == "prepared"
            assert shown["branches"]["played"]["supported"] == 1
            assert shown["branches"]["alternative"]["supported"] == 1
            app = create_app(
                db_path=db_path,
                project_root=root,
                subject="learner",
                actor="fixture",
                corpus="test",
                login="fixture",
                origin="https://coach.invalid",
            )
            route = f"/repertoire/games/{game_id}/openings/{position_id}/profile"
            client = app.test_client()
            assert client.get(route, base_url="https://coach.invalid").status_code == 403
            query = {
                "reference": "recent",
                "alternative": "b8c6",
                "proof_kind": "discovery_material",
            }
            page = client.get(
                route,
                query_string=query,
                base_url="https://coach.invalid",
                headers={"Tailscale-User-Login": "fixture"},
            )
            assert page.status_code == 200
            assert page.data.count(b"Public recorded discovery example") == 2
            assert b"Unplayed moves are unsearched" in page.data
            assert (
                b"Black played Nf3+" in page.data
                and b"bishop on c5 toward the queen on f2" in page.data
            )
            prefix_path = planning / PREFIX_NAME
            original_prefix = prefix_path.read_bytes()
            artifacts = set(planning.glob("opening-public-proof-*.json"))
            prefix_path.chmod(0o600)
            try:
                with prefix_path.open("r+b") as stream:
                    stream.write(bytes([original_prefix[0] ^ 1]))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                assert json.loads(output.getvalue())["public_preparation"] is None
                stale = client.get(
                    route,
                    query_string=query,
                    base_url="https://coach.invalid",
                    headers={"Tailscale-User-Login": "fixture"},
                )
                assert stale.status_code == 200
                assert b"No current recorded material discovery preparation" in stale.data
                assert b"Public recorded discovery example" not in stale.data
            finally:
                with prefix_path.open("r+b") as stream:
                    stream.write(original_prefix[:1])
                prefix_path.chmod(0o400)
            assert prefix_path.read_bytes() == original_prefix
            assert set(planning.glob("opening-public-proof-*.json")) == artifacts
        assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before


def _recent_defense_workflow(monkeypatch):
    from dataclasses import replace

    from chess_coach import discovery_defense_pipeline
    from chess_coach.discovery_defense_cursor import load
    from chess_coach.fork_worker_cursor import scan
    from chess_coach.material_source import prepare
    from chess_coach.pipeline_cursor import save_cursor

    class SyntheticEngine:
        def __init__(self):
            self.id, self.options = {"name": "fixture"}, {}

        def configure(self, _settings):
            pass

        def analyse(self, board, _limit, multipv, root_moves=None):
            move = root_moves[0] if root_moves else next(iter(board.legal_moves))
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": [move],
                    "nodes": 100,
                    "depth": 5,
                }
            ]

        def quit(self):
            pass

    db = Database(":memory:")
    db.initialize()
    for i in (1, 2, 3):
        ingest_pgn(
            db,
            f'''[Event "Fixture {i}"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:0{i}"]
[White "{LEARNER}"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *
''',
        )
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_max_scan=8,
        material_max_decisions=2,
    )
    engine_hash = engine_identity(sys.executable)
    seen = []

    def simulated(db, position, learner, *, exclusions, successes):
        prepare(db, position, learner)
        seen.append(position)
        exclusions["fixture_unresolved"] += 1
        return {"replayed": False, "outcome": "ambiguous"}

    with monkeypatch.context() as fake:
        fake.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: SyntheticEngine())
        fake.setattr(discovery_defense_pipeline, "combined", simulated)
        for game_id in (1, 2):
            assert (
                run_analysis(db, game_id, game_input(db, game_id), config, engine_hash)["status"]
                == "complete"
            )
        archive_key, _ = scan(
            db,
            LEARNER,
            1,
            namespace="discovery-mate-defense-cursor-v1:",
            policy=discovery_defense_pipeline.POLICY,
        )
        save_cursor(db, archive_key, 4, discovery_defense_pipeline.POLICY)
        first = discovery_defense_pipeline.process_defenses(db, config, engine_hash)
        assert first["limits"] == {"positions": 8, "decisions": 2}
        assert first["recent"]["processed"] == first["archive"]["processed"] == 1
        assert first["archive"]["overlap"] == 1 and len(seen) == len(set(seen))
        assert first["recent"]["source_unavailable"] == 1 and first["examined"] <= 8
        assert first["material_unresolved"]["fixture_unresolved"] == 2
        assert first["recent"]["material_unresolved"]["fixture_unresolved"] == 1
        first_state = load(db, LEARNER)
        first_archive = db.connection.execute(
            "SELECT last_game_id FROM pipeline_cursors WHERE account_key=?", (archive_key,)
        ).fetchone()[0]
        second = discovery_defense_pipeline.process_defenses(db, config, engine_hash)
        second_state = load(db, LEARNER)
        second_archive = db.connection.execute(
            "SELECT last_game_id FROM pipeline_cursors WHERE account_key=?", (archive_key,)
        ).fetchone()[0]
        assert second["recent"]["processed"] == 1 and second_state["last"] != first_state["last"]
        assert second_archive > first_archive and second["processed"] <= 2
        # An imported game becomes eligible once its ordinary analysis is current.
        assert run_analysis(db, 3, game_input(db, 3), config, engine_hash)["status"] == "complete"
        third = discovery_defense_pipeline.process_defenses(db, config, engine_hash)
        assert third["recent"]["processed"] == 1 and load(db, LEARNER)["last"] == 3
        game_input_hash = db.connection.execute(
            "SELECT input_hash FROM pipeline_stages WHERE game_id=2 AND stage='analysis'"
        ).fetchone()[0]
        db.connection.execute(
            "UPDATE pipeline_stages SET input_hash=? WHERE game_id=2 AND stage='analysis'",
            ("stale",),
        )
        db.connection.commit()
        stale = discovery_defense_pipeline.process_defenses(db, config, engine_hash)
        assert stale["recent"]["source_unavailable"] >= 1
        db.connection.execute(
            "UPDATE pipeline_stages SET input_hash=? WHERE game_id=2 AND stage='analysis'",
            (game_input_hash,),
        )
        db.connection.commit()
        small = replace(config, material_max_scan=1, material_max_decisions=1)
        recent_turn = discovery_defense_pipeline.process_defenses(db, small, engine_hash)
        archive_turn = discovery_defense_pipeline.process_defenses(db, small, engine_hash)
        assert recent_turn["recent"]["scanned"] and not recent_turn["archive"]["scanned"]
        assert archive_turn["archive"]["scanned"] and not archive_turn["recent"]["scanned"]
        assert recent_turn["processed"] <= 1 and archive_turn["processed"] <= 1

        before = dict(load(db, LEARNER)["positions"])
        interrupted = []

        def interrupt(_db, position, _learner, **_kwargs):
            interrupted.append(position)
            raise KeyboardInterrupt()

        fake.setattr(discovery_defense_pipeline, "combined", interrupt)
        with pytest.raises(KeyboardInterrupt):
            discovery_defense_pipeline.process_defenses(db, config, engine_hash)
        game_id = db.connection.execute(
            "SELECT game_id FROM positions WHERE id=?", (interrupted[0],)
        ).fetchone()[0]
        assert dict(load(db, LEARNER)["positions"])[game_id] == before.get(game_id, 0)
    db.close()
