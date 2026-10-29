"""The CLI and private browser share one truthful capability snapshot."""

import html
import json
import sys

from chess_coach.capabilities import capability_report
from chess_coach.cli import main
from chess_coach.web import create_app


def test_registry_is_scoped_unique_and_defensive():
    report = capability_report()
    entries = report["capabilities"]
    assert report["version"] == "1.53.0"
    assert len({item["id"] for item in entries}) == len(entries)
    assert {item["status"] for item in entries} == {"supported", "observation-only", "planned"}
    states = {item["id"]: item["status"] for item in entries}
    assert states["back_rank_observations"] == "observation-only"
    assert states["accessible_practice_board"] == "supported"
    assert states["direct_source_practice"] == "supported"
    assert states["licensed_public_collections"] == "supported"
    assert states["staged_puzzle_corpus"] == "supported"
    staged = next(item for item in entries if item["id"] == "staged_puzzle_corpus")
    assert "subset provenance" in staged["details"]
    assert states["manual_deep_selection"] == "supported"
    assert states["manual_deep_execution"] == "supported"
    structures = next(item for item in entries if item["id"] == "structures")
    assert structures["status"] == "observation-only"
    assert all(
        name in structures["details"]
        for name in (
            "IQP",
            "Carlsbad",
            "French",
            "Caro-Kann",
            "Benoni",
            "Maróczy",
            "Hedgehog",
            "Scheveningen",
            "Boleslavsky",
        )
    )
    assert states["automatic_deep_analysis"] == "supported"
    assert states["opening_classification"] == "observation-only"
    assert states["repertoire_recommendations"] == "planned"
    assert states["competency_graph"] == "supported"
    assert states["king_safety_lessons"] == "observation-only"
    assert states["pawn_structure_lessons"] == "observation-only"
    assert states["rook_plans"] == "observation-only"
    assert states["pawn_opportunities"] == "observation-only"
    assert states["manual_pawn_proof"] == "observation-only"
    assert states["manual_mate_proof"] == "observation-only"
    assert states["automatic_bounded_mate"] == "observation-only"
    assert states["mate_in_one_execute"] == "supported"
    assert states["tactical_geometry"] == "observation-only"
    assert states["fork_opportunities"] == "observation-only"
    assert states["fork_defense"] == "observation-only"
    assert states["pin_opportunities"] == "observation-only"
    assert states["material_opportunities"] == "observation-only"
    material = next(item for item in entries if item["id"] == "material_opportunities")
    assert "version 1.1.0" in material["details"]
    assert states["style_choices"] == "observation-only"
    assert states["own_game_practice"] == "observation-only"
    assert states["private_course_publication"] == "planned"
    entries[0]["name"] = "modified"
    assert capability_report()["capabilities"][0]["name"] != "modified"


def test_cli_and_private_browser_report_the_same_registry(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "unused.sqlite"
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(db_path), "capabilities"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report == capability_report()
    assert not db_path.exists()

    app = create_app(
        db_path=db_path,
        subject="learner",
        actor="operator",
        corpus="fixture-v1",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    app.testing = True
    client = app.test_client()
    assert client.get("/capabilities", base_url="https://coach.invalid").status_code == 403
    response = client.get(
        "/capabilities",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    page = response.get_data(as_text=True)
    assert report["version"] in page
    for item in report["capabilities"]:
        assert html.escape(item["name"]) in page
        assert html.escape(item["details"]) in page
        assert item["status"] in page
    assert not db_path.exists()
