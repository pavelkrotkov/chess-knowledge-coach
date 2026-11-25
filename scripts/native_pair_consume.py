"""Start a genuine practice form through the declared candidate handler."""

import json
import sys
from pathlib import Path


def consume(data):
    import chess_coach

    if Path(sys.prefix).resolve() != Path(data["prefix"]).resolve():
        raise ValueError("candidate interpreter mismatch")
    if not Path(chess_coach.__file__).resolve().is_relative_to(Path(data["source"]).resolve()):
        raise ValueError("candidate application mismatch")

    from chess_coach.db import Database
    from chess_coach.web import create_app

    subject = data["subject"]
    app = create_app(
        db_path=data["database"],
        project_root=data["root"],
        subject=subject,
        actor="fixture",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    page = client.get("/plan", base_url="https://coach.invalid", headers=headers)
    if page.status_code != 200:
        raise ValueError("candidate plan unavailable")
    form = json.loads(Path(data["form"]).read_text())
    with client.session_transaction(base_url="https://coach.invalid") as session:
        form["csrf"] = session["csrf"]
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=form,
    )
    if response.status_code != 303:
        raise ValueError("candidate refused the issued form")
    attempt = response.location.rstrip("/").rsplit("/", 1)[-1]
    db = Database(data["database"])
    try:
        row = db.connection.execute(
            """SELECT 1 FROM unified_sessions s JOIN unified_training_enrollments e
            ON e.attempt_id=s.attempt_id WHERE s.attempt_id=? AND s.subject=?
            AND s.source_type=? AND s.source_version=? AND s.source_key=? AND e.subject=?""",
            (attempt, subject, form["source_type"], form["version"], form["key"], subject),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise ValueError("candidate did not enroll the issued source")


if __name__ == "__main__":
    consume(json.load(sys.stdin))
    print("synthetic-form-started")
