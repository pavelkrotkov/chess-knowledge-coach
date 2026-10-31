"""The CLI and private browser share one truthful capability snapshot."""

import html
import json
import sys

from chess_coach.capabilities import capability_report
from chess_coach.cli import main
from chess_coach.web import create_app


def test_cli_and_private_browser_report_the_same_registry(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "unused.sqlite"
    monkeypatch.setattr(sys, "argv", ["chess-coach", "--db", str(db_path), "capabilities"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report == capability_report()
    assert (
        next(item for item in report["capabilities"] if item["id"] == "related_backrank_attack")[
            "status"
        ]
        == "observation-only"
    )
    assert (
        next(item for item in report["capabilities"] if item["id"] == "related_pin_execution")[
            "status"
        ]
        == "observation-only"
    )
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
