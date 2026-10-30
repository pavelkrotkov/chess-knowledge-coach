"""Owned pin prevention preserves bounded witnesses and immutable outcomes."""

import json
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.objective_pin_prevent_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_pin_pipeline import Engine

SUBJECT = "fixture_learner"
RELATIVE = "7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1"
ABSOLUTE = "7k/8/8/4r3/8/8/4R3/4K3 w - - 0 1"


def owned(path, monkeypatch, fen=RELATIVE, played="e2f2", black=False, unknown_history=False):
    board = chess.Board(fen)
    move = chess.Move.from_uci(played)
    if black:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    if unknown_history:
        board.halfmove_clock = 1
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
        }
    )
    node = game.add_variation(move)
    board.push(move)
    if not board.is_game_over():
        node.add_variation(next(iter(board.legal_moves)))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, SUBJECT, "prevent")
    assert result["outcome"] in {"success", "failure"}
    return db, result["evidence_ids"][0], result["outcome"]


def start_pin(db, evidence, attempt="pin-prevent"):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def mirror(move, black):
    move = chess.Move.from_uci(move)
    if black:
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    return move.uci()


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("source", ["success", "failure"])
@pytest.mark.parametrize("absolute", [False, True])
def test_existing_pin_source_both_outcomes_and_legal_responses(
    tmp_path, monkeypatch, black, source, absolute
):
    fen = ABSOLUTE if absolute else RELATIVE
    good = "e2e5" if absolute else "e2e3"
    bad = "e2e3" if absolute else "e2f2"
    db, evidence, outcome = owned(
        tmp_path / "pin.sqlite", monkeypatch, fen, good if source == "success" else bad, black
    )
    assert outcome == source
    before = {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in (
            "evidence_mappings",
            "evidence_review_events",
            "mastery_events",
            "mastery_states",
            "training_items",
            "training_attempts",
            "training_completions",
        )
    }
    state = start_pin(db, evidence)
    assert state["pin_prevent_origin"] == "existing"
    assert good not in json.dumps(state) and bad not in json.dumps(state)
    original = submit(db, "pin-prevent", SUBJECT, event_id="answer", move=mirror(good, black))
    assert original["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pin-prevent", "answer")["status"] == "correct"
    assert (
        submit(db, "pin-prevent", SUBJECT, event_id="answer", move=mirror(good, black)) == original
    )
    assert show(db, "pin-prevent", SUBJECT)["verification"]["status"] == "correct"
    start_pin(db, evidence, "bad")
    submit(db, "bad", SUBJECT, event_id="answer", move=mirror(bad, black))
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}
    result = json.loads(
        db.connection.execute(
            "SELECT result_json FROM objective_results WHERE attempt_id='bad'"
        ).fetchone()[0]
    )
    assert result["proof"]["mode"] in {"exposure", "pinned_capture"}
    assert {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in before
    } == before


def test_review_change_cancels_stale_publication_and_preserves_response(tmp_path, monkeypatch):
    import time

    from chess_coach.objective_publication import publish
    from chess_coach.objective_verify import compute

    db, evidence, _ = owned(tmp_path / "stale.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="other",
            subject="other",
            source_type="own-game",
            version=VERSION,
            key=str(evidence),
        )
    start_pin(db, evidence)
    original = submit(db, "pin-prevent", SUBJECT, event_id="answer", move="e2e3")
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    result = compute(db, request, time.monotonic)
    assert result["status"] == "correct"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    stored = publish(db, request, result)
    assert stored["status"] == "unresolved" and stored["reason"] == "source_unavailable"
    assert publish(db, request, result) == stored
    assert (
        json.loads(
            db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        )
        == original
    )
    with pytest.raises(ValueError):
        show(db, "pin-prevent", SUBJECT)


def test_private_browser_and_cli_play_and_queue(tmp_path, monkeypatch, capsys):
    from chess_coach.cli import main

    path = tmp_path / "browser.sqlite"
    db, evidence, _ = owned(path, monkeypatch)
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "list-pin-prevention", "--subject", SUBJECT]
    )
    main()
    assert json.loads(capsys.readouterr().out)["candidates"] == [{"key": str(evidence)}]

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "start-unified",
            "--attempt",
            "cli",
            "--subject",
            SUBJECT,
            "--source",
            "own-game",
            "--version",
            VERSION,
            "--key",
            str(evidence),
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["objective"] == "prevent_named_pin"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "move-unified",
            "--attempt",
            "cli",
            "--subject",
            SUBJECT,
            "--event",
            "cli-answer",
            "--move",
            "e2e3",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["feedback"] == "needs_verification"
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(path), "process-objective-verifications", "--subject", SUBJECT],
    )
    main()
    assert json.loads(capsys.readouterr().out)["outcomes"] == {"correct": 1}
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    app.testing = True
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login", "Origin": "https://coach.invalid"}
    response = client.get(
        f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
    )
    assert response.status_code == 200 and b"Practice pin prevention" in response.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": str(evidence)},
    )
    assert response.status_code == 303
    page = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Prevent the named pin consequence" in page.data and b"e2e3" not in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        attempt = session["unified_attempt"]
    played = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "attempt": attempt, "event": "answer", "move": "e2e3"},
    )
    assert played.status_code == 303
    worker = Database(path)
    assert process(worker, SUBJECT)["outcomes"] == {"correct": 1}
    worker.close()
    page = client.get(played.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"stated bounded pin defense is verified" in page.data


CREATED = "4r2k/b1p5/Bpnppppp/8/8/8/8/7K b - - 0 1"


def created_owned(path, monkeypatch, *, flipped, outcome):
    board = chess.Board(CREATED)
    good = mirror("e8f8", flipped)
    bad = mirror("h8g8", flipped)
    reply = mirror("a6c8", flipped)
    if flipped:
        board = board.mirror()
    root = board.board_fen()
    played = good if outcome == "success" else bad
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": SUBJECT if flipped else "fixture_opponent",
            "Black": "fixture_opponent" if flipped else SUBJECT,
            "Result": "*",
        }
    )
    node = game.add_variation(board.parse_uci(played))
    board.push_uci(played)
    node.add_variation(board.parse_uci(reply))

    class CreatedEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if board.board_fen() != root:
                return super().analyse(board, limit, multipv, root_moves)
            first = root_moves[0] if root_moves else board.parse_uci(good)
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": [first, chess.Move.from_uci(reply)],
                    "nodes": 100,
                    "depth": 5,
                }
            ]

    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: CreatedEngine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, SUBJECT, "prevent")
    assert result["outcome"] == outcome
    return db, result["evidence_ids"][0], good, bad


@pytest.mark.parametrize("flipped", [False, True])
@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_created_pin_source_defenses_and_bad_move(tmp_path, monkeypatch, flipped, outcome):
    db, evidence, good, bad = created_owned(
        tmp_path / "created.sqlite", monkeypatch, flipped=flipped, outcome=outcome
    )
    state = start_pin(db, evidence)
    assert state["pin_prevent_origin"] == "created"
    assert good not in json.dumps(state) and bad not in json.dumps(state)
    answer = submit(db, "pin-prevent", SUBJECT, event_id="good", move=good)
    assert answer["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    start_pin(db, evidence, "bad")
    submit(db, "bad", SUBJECT, event_id="bad", move=bad)
    assert process(db, SUBJECT)["outcomes"] == {"incorrect": 1}
    result = json.loads(
        db.connection.execute(
            "SELECT result_json FROM objective_results WHERE attempt_id='bad'"
        ).fetchone()[0]
    )
    assert result["reason"] == "named_created_pin_proved"
    assert result["proof"]["type"] == "relative_pin"

    board = chess.Board(state["fen"])
    board.push_uci(bad)
    board.push_uci(result["proof"]["move"])
    branches = result["proof"]["branches"]
    assert {item["reply"] for item in branches} == {m.uci() for m in board.legal_moves}
    for item in branches:
        after = board.copy(stack=True)
        after.push_uci(item["reply"])
        capture = chess.Move.from_uci(item["capture"])
        assert capture in after.legal_moves and after.is_capture(capture)
        after.push(capture)
        assert after.is_checkmate() == item["mate"]


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize("source", ["success", "failure"])
def test_checkmating_capture_of_pinner_is_qualified(tmp_path, monkeypatch, black, source):
    fen = "4k3/8/8/8/3R1R2/4rpp1/4R3/4Q2K w - - 0 1"
    good, bad = "e2e3", "e2d2"
    db, evidence, outcome = owned(
        tmp_path / "mate.sqlite", monkeypatch, fen, good if source == "success" else bad, black
    )
    assert outcome == source
    state = start_pin(db, evidence)
    move = chess.Move.from_uci(mirror(good, black))
    board = chess.Board(state["fen"])
    assert board.is_capture(move) and board.gives_check(move)
    board.push(move)
    assert board.is_checkmate()
    original = submit(db, "pin-prevent", SUBJECT, event_id="mate", move=move.uci())
    assert original["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}


@pytest.mark.parametrize("flipped", [False, True])
def test_created_pin_accepts_a_different_legal_defense(tmp_path, monkeypatch, flipped):
    db, evidence, original_good, _ = created_owned(
        tmp_path / "different.sqlite", monkeypatch, flipped=flipped, outcome="failure"
    )
    other = mirror("e8d8", flipped)
    assert original_good != other
    start_pin(db, evidence)
    submit(db, "pin-prevent", SUBJECT, event_id="other", move=other)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}


def test_work_reservations_cover_real_source_and_publication_calls(tmp_path, monkeypatch):
    from chess_coach import pin_capture_defense, pin_evidence, pin_exposure_geometry, pin_scan
    from chess_coach.objective_pin_prevent_limits import (
        ANSWER_CAPTURE_PROBES,
        ANSWER_PROOFS,
        SOURCE_CAPTURE_PROBES,
        SOURCE_PROOFS,
    )

    db, evidence, good, _ = created_owned(
        tmp_path / "budget.sqlite", monkeypatch, flipped=False, outcome="failure"
    )
    counts = {"proof": 0, "exposure": 0, "observer": 0}
    original_observer = pin_evidence.defense
    original_proof = pin_scan.proof
    original_exposure = pin_exposure_geometry.capture
    original_defense = pin_capture_defense.capture

    def observer(*args):
        counts["observer"] += 1
        return original_observer(*args)

    def proof(*args):
        counts["proof"] += 1
        return original_proof(*args)

    def exposure(*args):
        counts["exposure"] += 1
        return original_exposure(*args)

    def defense(*args):
        counts["exposure"] += 1
        return original_defense(*args)

    monkeypatch.setattr(pin_evidence, "defense", observer)
    monkeypatch.setattr(pin_scan, "proof", proof)
    monkeypatch.setattr(pin_exposure_geometry, "capture", exposure)
    monkeypatch.setattr(pin_capture_defense, "capture", defense)
    start_pin(db, evidence)
    assert counts["observer"] == 1
    assert 0 < counts["proof"] <= SOURCE_PROOFS
    assert counts["exposure"] <= SOURCE_CAPTURE_PROBES
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move=good)
    counts.update(proof=0, exposure=0, observer=0)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert counts["observer"] == 2
    assert 0 < counts["proof"] <= 2 * SOURCE_PROOFS + ANSWER_PROOFS
    assert counts["exposure"] <= 2 * SOURCE_CAPTURE_PROBES + ANSWER_CAPTURE_PROBES


def test_budget_rejects_excess_roots_and_kernel_drift(monkeypatch):
    from types import SimpleNamespace

    from chess_coach import pin_defense_success, pin_scan
    from chess_coach.objective_pin_prevent_preflight import reserve

    with pytest.raises(ValueError, match="work limit"):
        reserve(SimpleNamespace(legal_moves=range(65)))
    with monkeypatch.context() as patch:
        patch.setattr(pin_scan, "MAX_PINS", 17)
        with pytest.raises(ValueError, match="budget version"):
            reserve(chess.Board())
    monkeypatch.setattr(pin_defense_success, "MAX_COUNTERFACTUAL_ROOTS", 17)
    with pytest.raises(ValueError, match="budget version"):
        reserve(chess.Board())


def test_unknown_original_history_is_not_admitted(tmp_path, monkeypatch):
    db, evidence, _ = owned(tmp_path / "history.sqlite", monkeypatch, unknown_history=True)
    with pytest.raises(ValueError, match="history unavailable"):
        start_pin(db, evidence)


def test_created_scope_refuses_capture_check_and_other_immediate_mate():
    from chess_coach.objective_pin_prevent_created import judge

    named = {"attacker": "a6", "pinned": "c6", "rear": "e8", "kind": "relative_pin"}
    board = chess.Board(CREATED)
    board.set_piece_at(chess.B4, chess.Piece(chess.ROOK, chess.WHITE))
    capture = chess.Move.from_uci("c6b4")
    assert capture in board.legal_moves and board.is_capture(capture)
    assert judge(board, capture, named)[0] == "unresolved"

    board = chess.Board(CREATED)
    board.set_piece_at(chess.G3, chess.Piece(chess.QUEEN, chess.BLACK))
    checking = chess.Move.from_uci("g3g2")
    assert checking in board.legal_moves and board.gives_check(checking)
    assert judge(board, checking, named)[0] == "unresolved"

    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 b - - 0 1")
    move = board.parse_uci("c6a5")
    assert judge(board, move, named)[:2] == ("unresolved", "other_immediate_mate_unresolved")


def test_grounded_lesson_has_pin_prevention_entry(tmp_path):
    from flask import render_template

    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject="fixture",
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    lesson = {
        "family": "pin-prevent-mapper",
        "qualification": "bounded",
        "possible": "possible",
        "question": "question",
        "habit": "habit",
        "practice": "practice",
        "examples": [
            {
                "evidence_id": 1,
                "position_id": 1,
                "game_id": 1,
                "ply": 1,
                "review": "unreviewed",
                "played": "move",
                "operation": "prevent",
                "facts": [],
                "lines": [],
            }
        ],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson, csrf="fixture")
    assert "Practice pin prevention" in page and VERSION in page and "/unified/start" in page


def test_execute_version_cannot_admit_prevent_source(tmp_path, monkeypatch):
    from chess_coach.objective_pin_contract import VERSION as EXECUTE_VERSION

    db, evidence, _ = owned(tmp_path / "collision.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="collision",
            subject=SUBJECT,
            source_type="own-game",
            version=EXECUTE_VERSION,
            key=str(evidence),
        )
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 0


def test_changed_mapper_cannot_publish_old_result(tmp_path, monkeypatch):
    db, evidence, _ = owned(tmp_path / "mapper.sqlite", monkeypatch)
    start_pin(db, evidence)
    original = submit(db, "pin-prevent", SUBJECT, event_id="answer", move="e2e3")
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version='changed' WHERE id=(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
        (evidence,),
    )
    db.connection.commit()
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    saved = db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
    assert json.loads(saved) == original


def test_created_matching_tracks_the_original_piece_when_it_moves():
    from chess_coach.objective_pin_prevent_match import matches

    named = {"attacker": "a6", "pinned": "c6", "rear": "e8", "kind": "relative_pin"}
    defense = chess.Move.from_uci("e8f8")
    proof = {"move": "a6b5", "pinned": "c6", "rear": "f8", "type": "relative_pin"}
    assert matches(proof, defense, named)
    assert not matches({**proof, "rear": "e8"}, defense, named)
    assert not matches({**proof, "move": "b4b5"}, defense, named)


def test_recapturable_pinner_is_not_a_proved_defense():
    from chess_coach.objective_pin_prevent_existing import judge

    board = chess.Board("7k/5p2/8/8/3p4/4r3/4R2K/4Q3 w - - 0 1")
    named = {"attacker": "e3", "pinned": "e2", "rear": "e1", "kind": "relative_pin"}
    capture = board.parse_uci("e2e3")
    assert board.is_capture(capture)
    assert judge(board, capture, named)[0] == "unresolved"


@pytest.mark.parametrize("change", ["mapper", "link", "analysis", "review"])
def test_source_recheck_detects_changes_after_observation(tmp_path, monkeypatch, change):
    from chess_coach import objective_pin_prevent_source as source

    db, evidence, _ = owned(tmp_path / "source-race.sqlite", monkeypatch)
    original = source.snapshot

    def snapshot(*args):
        result = original(*args)
        if change == "mapper":
            db.connection.execute(
                "UPDATE mapping_runs SET mapper_version='changed' WHERE id=(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
                (evidence,),
            )
        elif change == "link":
            db.connection.execute(
                "UPDATE evidence_fact_links SET active=0 WHERE evidence_id=?", (evidence,)
            )
        elif change == "analysis":
            db.connection.execute(
                "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
            )
        else:
            review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
        return result

    monkeypatch.setattr(source, "snapshot", snapshot)
    with pytest.raises(ValueError, match="changed"):
        source.resolve(db, VERSION, str(evidence), SUBJECT)


def test_verifier_reports_timeout_and_malformed_binding():
    from chess_coach.objective_pin_prevent_judge import verify

    board = chess.Board(RELATIVE)
    move = board.parse_uci("e2e3")
    named = {
        "origin": "existing",
        "attacker": "e3",
        "pinned": "e2",
        "rear": "e1",
        "kind": "relative_pin",
    }
    request = {"learner_color": "white"}
    assert (
        verify(board, move, request, [], lambda: 6, 0, 5, {}, {"pin_prevention": named})["reason"]
        == "timeout"
    )
    ticks = iter([0, 6])
    assert (
        verify(board, move, request, [], lambda: next(ticks), 0, 5, {}, {"pin_prevention": named})[
            "reason"
        ]
        == "timeout"
    )
    assert (
        verify(
            board, move, request, [], lambda: 0, 0, 5, {}, {"pin_prevention": {"origin": "invalid"}}
        )["status"]
        == "unresolved"
    )
    assert (
        verify(
            board,
            move,
            {"learner_color": "black"},
            [],
            lambda: 0,
            0,
            5,
            {},
            {"pin_prevention": named},
        )["reason"]
        == "learner_turn_changed"
    )


def test_created_scan_limit_and_unavailable_are_unresolved(monkeypatch):
    from types import SimpleNamespace

    from chess_coach import objective_pin_prevent_created as created

    board = chess.Board(CREATED)
    move = board.parse_uci("e8f8")
    named = {"attacker": "a6", "pinned": "c6", "rear": "e8", "kind": "relative_pin"}
    with monkeypatch.context() as patch:
        patch.setattr(created, "quiet_after", lambda *_: SimpleNamespace(legal_moves=range(65)))
        assert created.judge(board, move, named)[1] == "defense_outside_supported_scope"
    monkeypatch.setattr(created, "scan", lambda _: None)
    assert created.judge(board, move, named)[1] == "pin_scan_unavailable"


def test_wrong_named_existing_pin_is_not_accepted():
    from chess_coach.objective_pin_prevent_existing import judge

    board = chess.Board(RELATIVE)
    move = board.parse_uci("e2e3")
    wrong = {"attacker": "e4", "pinned": "e2", "rear": "e1", "kind": "relative_pin"}
    assert judge(board, move, wrong)[1] == "named_existing_pin_unavailable"


@pytest.mark.parametrize("change", ["context", "detector"])
def test_source_recheck_rejects_context_and_detector_changes(tmp_path, monkeypatch, change):
    from chess_coach import objective_pin_prevent_source as source

    db, evidence, _ = owned(tmp_path / "data-race.sqlite", monkeypatch)
    original = source.snapshot

    def snapshot(*args):
        result = original(*args)
        if change == "context":
            row = db.connection.execute(
                "SELECT context_json FROM evidence_mappings WHERE id=?", (evidence,)
            ).fetchone()
            value = json.loads(row[0])
            value["fixture_changed"] = True
            db.connection.execute(
                "UPDATE evidence_mappings SET context_json=? WHERE id=?",
                (json.dumps(value), evidence),
            )
        else:
            run = db.connection.execute(
                "SELECT f.run_id FROM evidence_fact_links l JOIN detector_facts f ON f.id=l.fact_id WHERE l.evidence_id=?",
                (evidence,),
            ).fetchone()[0]
            row = db.connection.execute(
                "SELECT input_json FROM detector_runs WHERE id=?", (run,)
            ).fetchone()
            value = json.loads(row[0])
            value["detector_input"]["fixture_changed"] = True
            db.connection.execute(
                "UPDATE detector_runs SET input_json=? WHERE id=?", (json.dumps(value), run)
            )
        return result

    monkeypatch.setattr(source, "snapshot", snapshot)
    with pytest.raises(ValueError, match="changed"):
        source.resolve(db, VERSION, str(evidence), SUBJECT)


def test_worker_reserves_one_shared_budget_across_compute_and_publication(tmp_path, monkeypatch):
    from chess_coach import objective_fork_defense_budget as fork_budget
    from chess_coach import objective_pin_prevent_budget as budget
    from chess_coach import objective_pin_prevent_judge as judge
    from chess_coach import objective_pin_prevent_source as source

    db, evidence, good, _ = created_owned(
        tmp_path / "shared-budget.sqlite", monkeypatch, flipped=False, outcome="failure"
    )
    start_pin(db, evidence)
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move=good)
    calls = []
    source_take, answer_take = source.take_source, judge.take_answer

    def reserve_source():
        assert fork_budget.CURRENT.get() is None
        calls.append(("source", id(budget.CURRENT.get())))
        return source_take()

    def reserve_answer():
        assert fork_budget.CURRENT.get() is None
        calls.append(("answer", id(budget.CURRENT.get())))
        return answer_take()

    monkeypatch.setattr(source, "take_source", reserve_source)
    monkeypatch.setattr(judge, "take_answer", reserve_answer)
    result = process(db, SUBJECT)
    assert result["outcomes"] == {"correct": 1}
    assert result["pin_prevention_work_limit"] == {
        "requests": 1,
        "pin_proof_units_cap": 560,
        "exposure_capture_probe_units_cap": 323,
    }
    assert [kind for kind, _ in calls] == ["source", "answer", "source"]
    assert len({identity for _, identity in calls}) == 1
    assert budget.CURRENT.get() is None


def test_budget_exhaustion_before_publication_cannot_publish_correct(tmp_path, monkeypatch):
    from chess_coach import objective_pin_prevent_budget as budget

    db, evidence, good, _ = created_owned(
        tmp_path / "exhausted.sqlite", monkeypatch, flipped=False, outcome="failure"
    )
    start_pin(db, evidence)
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move=good)
    monkeypatch.setattr(budget, "PROOF_LIMIT", 288)
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "pin_proof_budget_exhausted"


def test_existing_result_recheck_keeps_original_result_immutable(tmp_path, monkeypatch):
    from chess_coach.objective_publication import publish

    db, evidence, _ = owned(tmp_path / "recheck.sqlite", monkeypatch)
    start_pin(db, evidence)
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move="e2e3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    stored = db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    result = publish(db, request, json.loads(stored))
    assert result["status"] == "unresolved" and result["reason"] == "source_unavailable"
    assert (
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0] == stored
    )


def test_mismatched_objective_is_rejected_before_source_work(tmp_path, monkeypatch):
    from chess_coach import objective_current

    db, evidence, _ = owned(tmp_path / "misroute.sqlite", monkeypatch)
    start_pin(db, evidence)
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move="e2e3")
    request = dict(db.connection.execute("SELECT * FROM objective_requests").fetchone())
    request["objective_version"] = "fork-defense-objective-v1"
    monkeypatch.setattr(objective_current, "require_current", lambda *_: pytest.fail("source work"))
    with pytest.raises(ValueError, match="source changed"):
        objective_current.current(db, request)


def test_pin_hint_assistance_is_retained(tmp_path, monkeypatch):
    from chess_coach.unified_session_events import hint

    db, evidence, _ = owned(tmp_path / "hint.sqlite", monkeypatch)
    start_pin(db, evidence)
    hint(db, "pin-prevent", SUBJECT, event_id="hint")
    submit(db, "pin-prevent", SUBJECT, event_id="answer", move="e2e3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pin-prevent", "answer")["assistance"] == "hinted"
