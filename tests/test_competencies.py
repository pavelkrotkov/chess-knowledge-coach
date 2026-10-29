"""Versioned competency graphs and honest, registry-backed coverage."""

import ast
import html
import json
import sys
from pathlib import Path

import pytest

from chess_coach.cli import main
from chess_coach.competency_coverage import competency_report
from chess_coach.competency_graph import seed_competency_graph, validate_graph
from chess_coach.competency_seed import EDGES, GRAPH_VERSION, SKILLS
from chess_coach.db import Database
from chess_coach.ontology import seed_ontology, skill_descendants
from chess_coach.web import create_app


def test_graph_preserves_old_versions_and_rejects_changed_version():
    db = Database(":memory:")
    db.initialize()
    seed_ontology(db, "legacy")
    assert seed_competency_graph(db) == len(SKILLS)
    assert seed_competency_graph(db) == len(SKILLS)
    assert "fork" in skill_descendants(db, "tactics", version="legacy")
    assert "back_rank_mate" in skill_descendants(db, "tactics", version=GRAPH_VERSION)
    with pytest.raises(ValueError, match="different contents"):
        seed_ontology(db, GRAPH_VERSION)
    db.connection.execute(
        "UPDATE skills SET description='altered' WHERE skill='fork' AND ontology_version=?",
        (GRAPH_VERSION,),
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="different contents"):
        seed_competency_graph(db)
    assert "fork" in skill_descendants(db, "tactics", version="legacy")


@pytest.mark.parametrize(
    "edges",
    [
        [("a", "missing", "requires")],
        [("a", "b", "unknown")],
        [("a", "b", "requires"), ("a", "b", "requires")],
        [("a", "b", "requires"), ("b", "a", "supports")],
    ],
)
def test_invalid_graph_is_rejected(edges):
    with pytest.raises(ValueError):
        validate_graph({"a": "A", "b": "B"}, edges)


def test_coverage_uses_real_capabilities_and_named_fixture_tests():
    report = competency_report()
    skills = {item["skill"]: item for item in report["skills"]}
    assert set(skills) == set(SKILLS)
    assert {item["status"] for item in skills.values()} == {
        "supported",
        "observation-only",
        "unsupported",
    }
    assert [item["skill"] for item in skills.values() if item["status"] == "supported"] == [
        "mate_in_one"
    ]
    mate = skills["mate_in_one"]
    assert (
        mate["operation"] == "execute" and mate["detector"] and mate["grading"] and mate["content"]
    )
    assert set(mate["fixtures"]) == {"positive", "negative", "ambiguous"}
    for ref in mate["fixtures"].values():
        path, name = ref.split("::")
        tree = ast.parse(Path(path).read_text())
        assert any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
            for node in tree.body
        )
    assert skills["fork"]["status"] == "observation-only" and not skills["fork"]["grading"]
    assert skills["back_rank_mate"]["status"] == "unsupported"
    assert skills["back_rank_mate"]["prerequisites"] == ["mate_in_one"]
    assert {edge["type"] for edge in report["edges"]} == {"contains", "requires", "supports"}
    assert len(report["edges"]) == len(EDGES)


def test_cli_and_private_browser_show_same_coverage(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "unused.sqlite"
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(db_path), "competencies"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report == competency_report()
    app = create_app(
        db_path=db_path,
        subject="learner",
        actor="operator",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    app.testing = True
    client = app.test_client()
    assert client.get("/competencies", base_url="https://coach.invalid").status_code == 403
    response = client.get(
        "/competencies",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    page = response.get_data(as_text=True)
    for item in report["skills"]:
        assert html.escape(item["description"]) in page and item["status"] in page
        for prerequisite in item["prerequisites"]:
            assert prerequisite in page
    assert not db_path.exists()


def test_seed_command_is_idempotent_and_rejects_open_transaction(tmp_path, monkeypatch, capsys):
    path = tmp_path / "graph.sqlite"
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(path), "seed-competencies"])
    main()
    assert json.loads(capsys.readouterr().out)["skills"] == len(SKILLS)
    main()
    assert json.loads(capsys.readouterr().out)["skills"] == len(SKILLS)
    db = Database(path)
    db.initialize()
    assert db.connection.execute(
        "SELECT count(*) FROM skills WHERE ontology_version = ?", (GRAPH_VERSION,)
    ).fetchone()[0] == len(SKILLS)
    db.connection.execute("BEGIN")
    with pytest.raises(RuntimeError, match="existing transaction"):
        seed_competency_graph(db)
    assert db.connection.in_transaction
    db.connection.rollback()
