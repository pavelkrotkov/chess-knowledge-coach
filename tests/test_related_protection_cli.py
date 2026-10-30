"""CLI entry point for protected defensive practice."""

import json
from argparse import Namespace

from chess_coach.cli_related_protection import begin, listing
from tests.related_protection_support import source_and_corpus
from tests.test_material_pipeline import LEARNER


def test_cli_lists_and_starts_only_the_selected_defense(tmp_path, monkeypatch, capsys):
    db, evidence = source_and_corpus(tmp_path / "cli.sqlite", monkeypatch)
    listing(db, Namespace(subject=LEARNER, evidence=evidence, corpus="test", cursor=None))
    result = json.loads(capsys.readouterr().out)
    assert len(result["items"]) == 1 and "line" not in result["items"][0]
    begin(
        db,
        Namespace(
            subject=LEARNER,
            evidence=evidence,
            corpus="test",
            attempt="cli",
            reference=result["items"][0]["reference"],
        ),
    )
    state = json.loads(capsys.readouterr().out)
    assert state["related_protection"] and state["protection_target"] == "d4"
    assert "source_key" not in state
