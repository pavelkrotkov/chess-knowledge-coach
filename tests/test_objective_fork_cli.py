"""Owned fork objectives remain concealed and verifiable through the CLI."""

import json
from argparse import Namespace

from chess_coach.cli_unified_practice import (
    handle_move,
    handle_start,
    handle_verify,
    handle_verify_status,
)
from tests.objective_fork_support import SUBJECT, VERSION, owned_fork


def test_cli_start_move_and_durable_alternative(tmp_path, monkeypatch, capsys):
    db, evidence = owned_fork(tmp_path / "cli.sqlite", monkeypatch, "f6g5")
    handle_start(
        db,
        Namespace(
            attempt="fork", subject=SUBJECT, source="own-game", version=VERSION, key=str(evidence)
        ),
    )
    initial = json.loads(capsys.readouterr().out)
    assert initial["fork_attacker"] == "b5" and "b5c7" not in json.dumps(initial)
    handle_move(db, Namespace(attempt="fork", subject=SUBJECT, event="answer", move="b5d6"))
    assert json.loads(capsys.readouterr().out)["status"] == "needs_verification"
    handle_verify(db, Namespace(subject=SUBJECT, limit=4))
    assert json.loads(capsys.readouterr().out)["outcomes"] == {"correct": 1}
    handle_verify_status(db, Namespace(subject=SUBJECT, attempt="fork", event="answer"))
    assert json.loads(capsys.readouterr().out)["status"] == "correct"
