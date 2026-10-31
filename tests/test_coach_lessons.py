"""Grounded coaching and immutable regeneration on synthetic sources."""

from chess_coach.fork_detector import process_decision
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


def test_repeated_failure_coaching_preview_is_private_and_historical(tmp_path, monkeypatch):
    import json
    import sys

    from chess_coach.db import Database
    from chess_coach.decision_inspection import inspect_decision
    from chess_coach.evidence_review import review_evidence
    from chess_coach.ingest import ingest_pgn
    from chess_coach.material_detector import process_decision as material_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app
    from tests.test_material_pipeline import LEARNER, make_game

    path = tmp_path / "coaching.sqlite"
    db = make_game(path, monkeypatch)
    first = material_decision(db, 1, LEARNER)["evidence_ids"][0]
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    assert "2026.01.01" in pgn
    ingest_pgn(db, pgn.replace("2026.01.01", "2026.01.02"))
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    material_decision(db, position, LEARNER)
    db.close()

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
    assert client.get("/coaching", base_url="https://coach.invalid").status_code == 403
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    assert b"Finding captures" in page.data and b"2 independent games" in page.data
    assert b"Source position before the move" in page.data and b'class="board"' in page.data
    assert b"Only 1 of three" in page.data and b"Recorded best-search continuation" in page.data
    check = Database(path)
    assert check.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    check.close()
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    assert (
        client.post(
            "/coaching/save", data={"csrf": csrf}, base_url="https://coach.invalid", headers=headers
        ).status_code
        == 403
    )
    saved = client.post(
        "/coaching/save",
        data={"csrf": csrf},
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
    )
    assert saved.status_code == 303
    snapshot = client.get(saved.location, base_url="https://coach.invalid", headers=headers)
    assert b"historical snapshot" in snapshot.data and b"Finding captures" in snapshot.data
    db = Database(path)
    saved_lesson = json.loads(
        db.connection.execute("SELECT lesson_json FROM lesson_versions").fetchone()[0]
    )
    example = saved_lesson["groups"][0]["lesson"]["examples"][0]
    decision = inspect_decision(db, example["position_id"], learner=LEARNER)
    assert example["fen"] == decision["decision_fen"]
    assert (
        example["fen"]
        != db.connection.execute(
            "SELECT fen FROM positions WHERE id=?", (example["position_id"],)
        ).fetchone()[0]
    )
    review_evidence(db, first, decision="reject", actor="fixture")
    db.close()
    page = client.get("/coaching", base_url="https://coach.invalid", headers=headers)
    assert b"Only 0 of three" in page.data
    assert (
        b"Finding captures"
        in client.get(saved.location, base_url="https://coach.invalid", headers=headers).data
    )
    history = client.get("/lessons", base_url="https://coach.invalid", headers=headers)
    assert b"Coaching preview / recurring patterns" in history.data
