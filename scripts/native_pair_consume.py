"""Start a genuine practice form through the declared candidate handler."""

import json
import sys
import traceback
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


def consume(data):
    import chess_coach

    if Path(sys.prefix).resolve() != Path(data["prefix"]).resolve():
        raise ValueError("candidate interpreter mismatch")
    if not Path(chess_coach.__file__).resolve().is_relative_to(Path(data["source"]).resolve()):
        raise ValueError("candidate application mismatch")

    import chess_coach.web_unified_practice as practice
    from chess_coach.db import Database
    from chess_coach.web import create_app

    subject = data["subject"]
    client = create_app(
        db_path=data["database"],
        project_root=data["root"],
        subject=subject,
        actor="fixture",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    ).test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    if client.get("/plan", base_url="https://coach.invalid", headers=headers).status_code != 200:
        raise ValueError("candidate plan unavailable")
    form = json.loads(Path(data["form"]).read_text())
    with client.session_transaction(base_url="https://coach.invalid") as session:
        form["csrf"] = session["csrf"]
    start_error = practice.start_error

    def report_error():
        traceback.print_exc()
        return start_error()

    with patch.object(practice, "start_error", report_error):
        response = client.post(
            "/unified/start",
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data=form,
        )
    if response.status_code != 303:
        raise ValueError("candidate refused the issued form")
    attempt = response.location.rstrip("/").rsplit("/", 1)[-1]
    with closing(Database(data["database"])) as db:
        if not db.connection.execute(
            """SELECT 1 FROM unified_sessions s JOIN unified_training_enrollments e
            ON e.attempt_id=s.attempt_id WHERE s.attempt_id=? AND s.subject=?
            AND s.source_type=? AND s.source_version=? AND s.source_key=? AND e.subject=?""",
            (attempt, subject, form["source_type"], form["version"], form["key"], subject),
        ).fetchone():
            raise ValueError("candidate did not enroll the issued source")


if __name__ == "__main__":
    consume(json.load(sys.stdin))
    print("synthetic-form-started")
