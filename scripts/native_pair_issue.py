"""Issue a genuine opening form from the declared candidate release."""

import json
import os
import runpy
import sys
from pathlib import Path


def issue(data):
    import chess_coach

    if Path(sys.prefix).resolve() != Path(data["prefix"]).resolve():
        raise ValueError("candidate interpreter mismatch")
    if not Path(chess_coach.__file__).resolve().is_relative_to(Path(data["source"]).resolve()):
        raise ValueError("candidate application mismatch")

    from chess_coach.curriculum_window_cursor import decode
    from chess_coach.db import Database
    from chess_coach.web import create_app

    app = create_app(
        db_path=data["database"],
        project_root=data["root"],
        subject="learner",
        actor="fixture",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/plan",
        query_string={"opening": data["choice"], "goal": "fork", "minutes": "5"},
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    form = runpy.run_path(data["parser"], run_name="native_pair_forms")["_form"](response)
    db = Database(data["database"])
    try:
        window = decode(db, form["opening_window_cursor"])
    finally:
        db.close()
    if window["v"] != 7 or window["state"]["v"] != data["inner_version"]:
        raise ValueError("unexpected candidate cursor version")
    form.pop("csrf", None)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(data["output"], flags, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(form, output)


if __name__ == "__main__":
    issue(json.load(sys.stdin))
    print("synthetic-opening-form-issued")
