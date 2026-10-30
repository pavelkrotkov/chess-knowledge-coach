"""Synthetic owned protection source with standard-start game history."""

import io

import chess
import chess.engine
import chess.pgn
import pytest

import tests.test_deep_selection as selection_tests
from chess_coach.deep_execution_worker import run_deep
from chess_coach.deep_selection import select_deep
from chess_coach.material_detector import process_decision
from chess_coach.objective_protection_contract import VERSION
from chess_coach.objective_protection_source import resolve
from tests.test_deep_execution import DeepEngine, options, use_engine

PGN = """[Event "Synthetic"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. b3 e5 2. d3 Nc6 3. Nf3 Nf6 4. g3 d5 5. Bg2 Bd6 6. O-O O-O
7. b4 h6 8. b5 Ne7 9. Nc3 Re8 10. Rb1 Bb4 11. Na4 *
"""


def continuation(board, move):
    replay = board.copy()
    result = [move]
    replay.push(move)
    for _ in range(3):
        choices = [
            m for m in replay.legal_moves if not replay.is_capture(m) and not replay.gives_check(m)
        ]
        if not choices:
            break
        move = choices[0]
        result.append(move)
        replay.push(move)
    return result


def fixture(path, monkeypatch, black=False):
    game = chess.pgn.read_game(io.StringIO(PGN))
    assert game is not None
    if black:
        mirrored = chess.pgn.Game()
        mirrored.headers["Event"] = "Synthetic"
        mirrored.headers["White"] = "fixture_opponent"
        mirrored.headers["Black"] = "fixture_learner"
        node = mirrored.add_variation(chess.Move.from_uci("g2g3"))
        for move in game.mainline_moves():
            node = node.add_variation(
                chess.Move(
                    chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
                )
            )
        game = mirrored
    played = list(game.mainline_moves())
    target_index = 21 if black else 20
    target_move = "c6a5" if black else "c3a4"
    capture_move = "b8b5" if black else "b1b4"

    class Engine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            roots = root_moves or [played[len(board.move_stack)]]
            if root_moves is None and len(board.move_stack) == target_index:
                roots = [chess.Move.from_uci(target_move), chess.Move.from_uci(capture_move)]
            elif root_moves is None and multipv > 1:
                roots += [m for m in board.legal_moves if m not in roots][: multipv - 1]
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": continuation(board, move),
                    "nodes": 200,
                    "depth": 5,
                    "time": 0.05,
                }
                for move in roots
            ]

    monkeypatch.setattr(selection_tests, "PGN", str(game))
    monkeypatch.setattr(selection_tests, "Engine", Engine)
    db = selection_tests.setup_game(path, monkeypatch)
    learner = selection_tests.LEARNER
    selected = select_deep(db, [1], learner=learner, per_game=100, total=100)
    use_engine(monkeypatch, Engine(db))
    run_deep(
        db,
        selected["games"][0]["selection_id"],
        learner=learner,
        options=options(multipv=2, max_jobs=30),
    )
    position_id = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=?", (target_index + 1,)
    ).fetchone()[0]
    result = process_decision(db, position_id, learner)
    assert result["evidence_ids"]
    return db, learner, position_id, result["evidence_ids"][0]


@pytest.mark.parametrize("black", [False, True])
def test_owned_full_history_has_current_protection_evidence(tmp_path, monkeypatch, black):
    db, learner, position_id, evidence = fixture(
        tmp_path / "source.sqlite", monkeypatch, black=black
    )
    state = resolve(db, VERSION, str(evidence), learner)
    assert state["provenance"]["position_id"] == position_id
    assert state["provenance"]["objective_target"] == ("c6" if black else "c3")
    db.close()


def test_owned_source_reaches_bounded_comparable_protection_report(tmp_path, monkeypatch):
    from chess_coach.style_report import style_report

    db, learner, position_id, evidence = fixture(tmp_path / "report.sqlite", monkeypatch)
    report = style_report(db, learner)
    matching = [item for item in report["observations"] if item["position_id"] == position_id]
    assert len(matching) == 1
    choice = matching[0]
    assert choice["choices"]["protect_move_target"] == "moved_target"
    assert choice["choices"]["protect_capture_attacker"] == "did_not_capture_attacker"
    assert report["protection_coverage"]["completed"] == 1
    pair = choice["pairs"][0]
    assert pair["played"]["protection"]["evidence_id"] == evidence
    assert pair["played"]["protection"]["target"] == "c3"
    assert pair["alternative"]["protection"]["captured_attacker"]
    db.close()


def test_budget_exhaustion_never_starts_source_resolution(tmp_path, monkeypatch):
    import importlib

    module = importlib.import_module("chess_coach.style_report")
    import chess_coach.style_protection_snapshot as snapshot

    db, learner, position_id, _evidence = fixture(tmp_path / "limited.sqlite", monkeypatch)
    monkeypatch.setattr(module, "PROTECTION_WORK_LIMIT", 0)
    monkeypatch.setattr(snapshot, "reference", lambda *args: pytest.fail("unexpected lookup"))
    report = module.style_report(db, learner)
    choice = next(item for item in report["observations"] if item["position_id"] == position_id)
    assert choice["choices"]["protect_move_target"] == "ambiguous"
    assert report["protection_coverage"]["used"] == 0
    assert report["protection_coverage"]["skipped_decisions"] > 0
    db.close()


def test_review_revocation_makes_the_next_report_unknown(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.style_report import style_report

    db, learner, position_id, evidence = fixture(tmp_path / "revoked.sqlite", monkeypatch)
    foreign = style_report(db, "fixture_other")
    assert not foreign["observations"] and foreign["protection_coverage"]["considered"] == 0
    before = style_report(db, learner)
    item = next(item for item in before["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_move_target"] == "moved_target"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    after = style_report(db, learner)
    item = next(item for item in after["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_move_target"] == "ambiguous"
    assert after["dimensions"]["protect_move_target"]["opportunities"] == 0
    db.close()


def test_changed_deep_source_rejects_protection_before_any_proof(tmp_path, monkeypatch):
    import chess_coach.style_protection_snapshot as snapshot
    from chess_coach.style_report import style_report

    db, learner, position_id, _evidence = fixture(tmp_path / "deep.sqlite", monkeypatch)
    monkeypatch.setattr(snapshot, "_same_deep", lambda *args: False)
    report = style_report(db, learner)
    item = next(item for item in report["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_move_target"] == "ambiguous"
    assert report["protection_coverage"]["proofs"] == 0
    db.close()


def test_snapshot_review_change_is_visible_on_the_next_request(tmp_path, monkeypatch):
    import chess_coach.style_protection_collect as collect
    from chess_coach.db import Database
    from chess_coach.evidence_review import review_evidence
    from chess_coach.style_report import style_report

    path = tmp_path / "concurrent.sqlite"
    db, learner, position_id, evidence = fixture(path, monkeypatch)
    db.connection.execute("PRAGMA journal_mode=WAL")
    writer = Database(path)
    original = collect.proof
    changed = False

    def proof_with_rejection(*args):
        nonlocal changed
        result = original(*args)
        if not changed:
            review_evidence(writer, evidence, decision="reject", actor="fixture_reviewer")
            changed = True
        return result

    monkeypatch.setattr(collect, "proof", proof_with_rejection)
    first = style_report(db, learner)
    item = next(item for item in first["observations"] if item["position_id"] == position_id)
    assert changed and item["choices"]["protect_move_target"] == "moved_target"
    second = style_report(db, learner)
    item = next(item for item in second["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_move_target"] == "ambiguous"
    writer.close()
    db.close()


def test_source_report_is_private_and_has_citations(tmp_path, monkeypatch, capsys):
    import json
    import sys

    from chess_coach.cli import main
    from chess_coach.db import Database
    from chess_coach.web import create_app

    path = tmp_path / "browser.sqlite"
    db, learner, position_id, evidence = fixture(path, monkeypatch)
    tables = (
        "evidence_mappings",
        "evidence_review_events",
        "mastery_states",
        "mastery_events",
        "training_items",
        "training_attempts",
    )
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", learner]
    )
    main()
    report = json.loads(capsys.readouterr().out)
    item = next(item for item in report["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_capture_attacker"] == "did_not_capture_attacker"
    assert item["pairs"][0]["alternative"]["protection"]["captured_piece"] == "bishop"
    assert item["pairs"][0]["alternative"]["protection"]["guard"] == "unknown"
    assert "source_fingerprint" not in item["pairs"][0]["played"]["protection"]["source"]
    app = create_app(
        db_path=path,
        subject=learner,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/style-choices", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/style-choices",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
    )
    assert page.status_code == 200
    assert b"Capturing the immediate attacker" in page.data
    assert b"captures bishop on b4" in page.data
    assert b"Guard status unknown" in page.data
    assert f"/evidence/{evidence}".encode() in page.data
    db = Database(path)
    after = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    assert before == after
    db.close()


@pytest.mark.parametrize("black", [False, True])
def test_source_linked_contrast_is_qualified_for_both_colors(tmp_path, monkeypatch, black):
    from chess_coach.style_report import style_report

    db, learner, position_id, _evidence = fixture(
        tmp_path / "colors.sqlite", monkeypatch, black=black
    )
    report = style_report(db, learner)
    item = next(item for item in report["observations"] if item["position_id"] == position_id)
    assert item["context"]["color"] == ("black" if black else "white")
    assert item["choices"]["protect_move_target"] == "moved_target"
    assert item["choices"]["protect_capture_attacker"] == "did_not_capture_attacker"
    db.close()


def test_changed_source_at_final_recheck_suppresses_choice(tmp_path, monkeypatch):
    import chess_coach.style_protection_source as source
    from chess_coach.style_report import style_report

    db, learner, position_id, _evidence = fixture(tmp_path / "changed-source.sqlite", monkeypatch)
    original = source.current

    def changed(*args, **kwargs):
        view, review = original(*args, **kwargs)
        return {**view, "source_fingerprint": "changed-synthetic-fingerprint"}, review

    monkeypatch.setattr(source, "current", changed)
    report = style_report(db, learner)
    item = next(item for item in report["observations"] if item["position_id"] == position_id)
    assert item["choices"]["protect_move_target"] == "ambiguous"
    assert report["dimensions"]["protect_move_target"]["opportunities"] == 0
    db.close()
