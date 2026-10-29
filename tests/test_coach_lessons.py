"""Grounded coaching and immutable regeneration on synthetic sources."""

import json

from chess_coach.fork_detector import process_decision
from chess_coach.lesson_generator import generate
from chess_coach.lesson_history import get, save
from chess_coach.lesson_mechanisms import describe
from chess_coach.lesson_source import source
from tests.test_fork_pipeline import LEARNER, make_game


def test_fork_lesson_uses_rechecked_fact_and_legal_line(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    candidate = {"id": evidence_id, "position_id": 1}
    current = source(db, LEARNER, candidate)
    example = describe(current)
    assert example["played"] != "Nc7+"
    assert "Nc7+" in example["facts"][0]
    assert example["evidence_id"] == evidence_id
    assert source(db, "another", candidate) is None
    db.connection.execute(
        "UPDATE detector_runs SET status='superseded' WHERE id=?", (result["detector_run_id"],)
    )
    db.connection.commit()
    assert source(db, LEARNER, candidate) is None


def test_generator_rejects_claims_and_preserves_history(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    lesson = {"examples": [{"position_id": 1, "facts": ["Only a verified fact."]}]}
    rejected, provenance = generate(
        db, lesson, lambda _: '{"order":[0],"claim":"invented"}', model="fixture"
    )
    assert rejected == lesson and provenance["status"] == "fallback"
    assert db.connection.execute("SELECT COUNT(*) FROM llm_explanations").fetchone()[0] == 0
    generated, provenance = generate(
        db, lesson, lambda _: json.dumps({"order": [0]}), model="fixture"
    )
    assert generated == lesson and provenance["status"] == "validated"
    first = save(db, LEARNER, lesson, inputs={"fixture": True})
    second = save(db, LEARNER, generated, model="fixture", inputs=provenance)
    db.connection.commit()
    assert first != second
    assert get(db, LEARNER, first)["lesson"] == lesson
    assert get(db, LEARNER, second)["inputs"]["status"] == "validated"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0


def test_decision_and_saved_history_render_coaching(tmp_path, monkeypatch):
    import chess_coach.web_lessons as web_lessons
    from chess_coach.web import create_app

    path = tmp_path / "synthetic.sqlite"
    db, _ = make_game(path, monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    from chess_coach.evidence_review import review_evidence

    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    db.close()
    group = {
        "skill": "fork",
        "operation": "execute",
        "family": "fork-opportunity-mapper",
        "version": "1.0.1",
        "lesson_examples": [
            {
                "id": evidence_id,
                "position_id": 1,
                "context": {
                    "side": "white",
                    "phase": "low material",
                    "clock": "unknown",
                    "time control": "unknown",
                },
            }
        ],
    }
    report_data = {
        "current": [group],
        "previous": [],
        "start": "s",
        "end": "e",
        "compare_start": "p",
        "skill": None,
        "operation": None,
    }
    monkeypatch.setattr(web_lessons, "report", lambda *args, **kwargs: report_data)
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    report_page = client.get("/recurrence", base_url="https://coach.invalid", headers=headers)
    assert b"not repeated mistakes" in report_page.data
    view = client.get("/decisions/1", base_url="https://coach.invalid", headers=headers)
    assert view.status_code == 200
    assert b"Diagnostic question" in view.data and b"Nc7+" in view.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    form = {
        "csrf": csrf,
        "start": "s",
        "end": "e",
        "compare_start": "p",
        "period": "current",
        **{key: group[key] for key in ("skill", "operation", "family", "version")},
    }
    headers["Origin"] = "https://coach.invalid"
    first = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    second = client.post(
        "/lessons/regenerate", data=form, base_url="https://coach.invalid", headers=headers
    )
    assert first.status_code == second.status_code == 303
    assert first.location != second.location
    page = client.get(first.location, base_url="https://coach.invalid", headers=headers)
    assert b"historical snapshot" in page.data and b"Nc7+" in page.data
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert history.status_code == 200 and history.data.count(b"fork / execute") == 2
    from chess_coach.db import Database

    check = Database(path)
    assert (
        check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 1
    )
    check.close()


def test_material_and_mate_sources_generate_specific_legal_explanations(tmp_path, monkeypatch):
    from chess_coach.mate_auto import process_decision as mate_decision
    from chess_coach.material_detector import process_decision as material_decision
    from tests.test_mate_proof import owned_game
    from tests.test_material_pipeline import LEARNER as MATERIAL_LEARNER
    from tests.test_material_pipeline import make_game as material_game

    db = material_game(tmp_path / "material.sqlite", monkeypatch)
    material = material_decision(db, 1, MATERIAL_LEARNER)
    evidence_id = material["evidence_ids"][0]
    example = describe(source(db, MATERIAL_LEARNER, {"id": evidence_id, "position_id": 1}))
    assert example["facts"] and example["lines"]
    assert all(line["moves"] for line in example["lines"])
    db.close()
    db = owned_game(tmp_path / "mate.sqlite", monkeypatch)
    mate_decision(db, 1, "fixture_a")
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE mapping_run_id IS NOT NULL"
    ).fetchone()
    example = describe(source(db, "fixture_a", {"id": row["id"], "position_id": 1}))
    assert "forced mating" in example["facts"][0]
    assert example["lines"]


def test_back_rank_source_produces_replayable_mate_line(tmp_path, monkeypatch):
    from chess_coach.back_rank_auto import process_decision as backrank_decision
    from chess_coach.mate_auto import process_decision as mate_decision
    from tests.test_back_rank import DEFENSE
    from tests.test_mate_proof import owned_game

    db = owned_game(tmp_path / "backrank.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    mate_decision(db, 1, "fixture_a")
    backrank_decision(db, 1, "fixture_a")
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank'"
    ).fetchone()
    example = describe(source(db, "fixture_a", {"id": row["id"], "position_id": 1}))
    assert "back-rank" in example["facts"][0]
    assert any(len(line["moves"]) == 2 for line in example["lines"])


def test_fork_defense_source_has_a_legal_counterfactual(tmp_path, monkeypatch):
    from chess_coach.fork_defense_detector import process_decision
    from tests.test_fork_defense_pipeline import LEARNER, make_game

    db, _ = make_game(tmp_path / "defense.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    example = describe(source(db, LEARNER, {"id": result["evidence_ids"][0], "position_id": 1}))
    assert "fork" in example["facts"][0]
    assert len(example["lines"][0]["moves"]) == 2
    db.close()
    db, _ = make_game(tmp_path / "defense-failure.sqlite", monkeypatch, failure=True)
    result = process_decision(db, 1, LEARNER)
    example = describe(source(db, LEARNER, {"id": result["evidence_ids"][0], "position_id": 1}))
    assert "recorded engine continuation" in example["facts"][0]
    assert len(example["lines"][0]["moves"]) == 2


def test_pawn_lesson_drops_illegal_choices():
    import chess

    from chess_coach.lesson_proofs import _pawn

    fen = "8/8/8/8/2k5/4K3/3P4/8 w - - 0 1"
    evidence = {"pawn_explanation": {"preserving": ["Ke4", "Ke9"]}}
    facts, lines = _pawn(evidence, fen)
    assert "preserves" in facts[0]
    assert lines[0]["moves"] == ["Ke4"] and lines[1] is None
    assert chess.Board(fen).parse_san(lines[0]["moves"][0]) in chess.Board(fen).legal_moves


def test_sparse_lesson_and_provider_errors_are_private(tmp_path, monkeypatch, caplog):
    from chess_coach.lesson_narrative import build

    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    monkeypatch.setattr("chess_coach.lesson_narrative.source", lambda *_: None)
    group = {
        "skill": "fork",
        "operation": "execute",
        "family": "fork-opportunity-mapper",
        "version": "1.0.1",
        "lesson_examples": [{"id": 1}],
    }
    lesson = build(db, LEARNER, group)
    assert lesson["examples"] == [] and lesson["question"]
    lesson["examples"] = [{"position_id": 1}]

    def fail(_):
        raise RuntimeError("sensitive-provider-error")

    result, provenance = generate(db, lesson, fail, model="fixture")
    assert result == lesson and provenance["status"] == "fallback"
    assert "sensitive-provider-error" not in caplog.text
    db.connection.execute("BEGIN")
    result, provenance = generate(db, lesson, fail, model="fixture")
    assert provenance["status"] == "fallback" and db.connection.in_transaction
    db.connection.rollback()


def test_invalid_acceptance_is_not_presented_as_accepted(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence

    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    db.connection.execute(
        "UPDATE evidence_mappings SET human_validated=0 WHERE id=?", (evidence_id,)
    )
    db.connection.commit()
    item = describe(source(db, LEARNER, {"id": evidence_id, "position_id": 1}))
    assert item["review"] == "invalid acceptance"


def test_pawn_lesson_uses_current_proof_source(tmp_path, monkeypatch):
    import chess

    from chess_coach.pawn_coach_detector import process_decision
    from chess_coach.pawn_proof import inspect
    from tests.test_mate_proof import owned_game
    from tests.test_pawn_coaching import FEN

    proof = inspect(chess.Board(FEN))
    db = owned_game(tmp_path / "pawn.sqlite", monkeypatch, fen=FEN, move="d4")
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    result = process_decision(db, 1, "fixture_a")
    item = describe(source(db, "fixture_a", {"id": result["evidence_ids"][0], "position_id": 1}))
    assert item["played"] == "d4"
    assert any(line["moves"] == ["Ke4"] for line in item["lines"])
    assert any("classified failure" in fact for fact in item["facts"])


def test_valid_generator_orders_examples_and_records_exact_inputs(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "synthetic.sqlite", monkeypatch)
    lesson = {
        "examples": [
            {"position_id": 1, "evidence_id": 10, "fact_id": 20},
            {"position_id": 1, "evidence_id": 11, "fact_id": 21},
        ]
    }
    output, provenance = generate(db, lesson, lambda _: '{"order":[1,0]}', model="fixture-model")
    assert [item["evidence_id"] for item in output["examples"]] == [11, 10]
    assert provenance["status"] == "validated"
    row = db.connection.execute(
        "SELECT model, prompt_version, prompt_json, response FROM llm_explanations"
    ).fetchone()
    assert row["model"] == "fixture-model" and row["prompt_version"] == "lesson-order-v1"
    assert json.loads(row["prompt_json"])["facts"]["lesson"] == lesson
    assert json.loads(row["response"]) == {"order": [1, 0]}
