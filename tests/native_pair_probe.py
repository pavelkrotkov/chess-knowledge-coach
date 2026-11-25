"""Fresh-process check for the same-database native-pair fixture."""

import hashlib
import json
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path

TABLES = (
    "unified_sessions",
    "unified_session_events",
    "unified_training_enrollments",
    "unified_training_completions",
    "training_items",
    "training_attempts",
    "training_completions",
    "puzzle_sessions",
    "puzzle_session_events",
    "objective_results",
)
ATTEMPTS = {
    "v6-hanging_piece": ("own-game", "capture_named_target", "unified_owned_capture"),
    "v6-fork": ("own-game", "execute_named_fork", "unified_owned_fork"),
    "v6-mate_in_one": ("public", "public_mate_in_one_standalone_v1", "unified_public_m1"),
    "prior-promotion": ("public", "promote_now", "unified_canonical_promotion"),
    "v6-promotion": ("public", "force_promotion_within_two", "unified_canonical_forced_promotion"),
    "native-pair-corpus": ("corpus", "corpus_mate_in_one", "unified_corpus_m1"),
}


def fingerprints(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        result = {}
        for table in TABLES:
            rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            typed = [[(type(value).__name__, repr(value)) for value in row] for row in rows]
            result[table] = hashlib.sha256(
                json.dumps(typed, separators=(",", ":"), ensure_ascii=True).encode()
            ).hexdigest()
        return result
    finally:
        connection.close()


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.forms = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("method") == "post":
            self.current = {}
        elif tag == "input" and self.current is not None and values.get("name"):
            self.current[values["name"]] = values.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


def _records(db):
    from chess_coach.unified_session_events import show

    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 41
    assert db.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    for attempt, expected in ATTEMPTS.items():
        row = db.connection.execute(
            """SELECT s.source_type,s.objective,t.source_type FROM unified_sessions s
            JOIN unified_training_enrollments e ON e.attempt_id=s.attempt_id
            JOIN training_items t ON t.id=e.item_id WHERE s.attempt_id=? AND s.subject=?""",
            (attempt, "fixture_learner"),
        ).fetchone()
        assert row is not None and tuple(row) == expected
        assert show(db, attempt, "fixture_learner")["learning"]["outcome"] == "success"
    assert (
        db.connection.execute(
            "SELECT count(*) FROM training_items WHERE source_type='puzzle'"
        ).fetchone()[0]
        > 0
    )


def _opening(payload, path, root):
    from chess_coach.web import create_app

    app = create_app(
        db_path=path,
        project_root=root,
        subject=payload.get("subject", "learner"),
        actor="fixture",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    response = client.get(
        "/plan",
        query_string={"opening": payload["choice"], "goal": "fork", "minutes": "5"},
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    form = _form(response)
    from chess_coach.curriculum_window_cursor import decode
    from chess_coach.db import Database

    db = Database(path)
    try:
        window = decode(db, form["opening_window_cursor"])
        assert window["v"] == 7 and window["state"]["v"] == 8
    finally:
        db.close()


def _form(response):
    assert response.status_code == 200
    assert b"opening experiment itself is not graded" in response.data, response.get_data(
        as_text=True
    )
    forms = Forms()
    forms.feed(response.get_data(as_text=True))
    return _inputs([form for form in forms.forms if form.get("opening_token")])


def _inputs(selected):
    from chess_coach.objective_fork_contract import MISS_VERSION

    assert len(selected) == 1
    form = selected[0]
    assert form.get("source_type") == "own-game"
    assert form.get("version") == MISS_VERSION
    assert form.get("training") == "1" and form.get("window_offer")
    assert form.get("opening_window_cursor")
    return form


def check(payload):
    import chess_coach
    from chess_coach.db import Database

    path, root = Path(payload["database"]), Path(payload["root"])
    assert Path(chess_coach.__file__).resolve() == Path(payload["application"]).resolve()
    assert fingerprints(path) == payload["fingerprints"]
    db = Database(path)
    try:
        _records(db)
    finally:
        db.close()
    _opening(payload, path, root)
    assert fingerprints(path) == payload["fingerprints"]


def main():
    payload = json.load(sys.stdin)
    check(payload)
    print("same-database-opening-verified")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        trace = exc.__traceback__
        while trace and trace.tb_next:
            trace = trace.tb_next
        line = trace.tb_lineno if trace else 0
        print("fixture-probe-failed", type(exc).__name__, line, file=sys.stderr)
        raise SystemExit(1) from None
