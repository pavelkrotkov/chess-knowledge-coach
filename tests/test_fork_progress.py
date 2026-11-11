"""Compare certified fork attempts without modifying learning state."""

import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import chess
import pytest

from chess_coach.objective_worker import process
from chess_coach.unified_session_events import reveal, submit
from chess_coach.web import create_app
from tests.objective_fork_support import SUBJECT, owned_fork


def test_certified_fork_progress_workflow(tmp_path, monkeypatch):
    from chess_coach import objective_fork_judge, related_fork_cache
    from chess_coach.fork_progress_report import report
    from chess_coach.related_fork_assessment_finder import find
    from chess_coach.related_fork_assessment_start import start

    path = tmp_path / "progress.sqlite"
    db, evidence = owned_fork(path, monkeypatch, "f6g5")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('progress','fixture','checksum','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    for index in range(20):
        board = chess.Board("b3k3/4B2p/5K2/1N3b2/8/8/8/8 b - - 0 1")
        for bit, square in enumerate((chess.A2, chess.B2, chess.D2, chess.E2, chess.F2)):
            if index & (1 << bit):
                board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
        key = f"synthetic-{index:02}"
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid','h7h6 b5c7 e8d7 c7a8',1200,80,'["fork"]','unknown')""",
            (key, corpus, board.fen()),
        )
        db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'fork',1200)", (corpus, key))
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    db.connection.commit()
    secret = b"synthetic-secret"
    assert report(db, SUBJECT, "progress")["status"] == "sparse"

    for index in range(20):
        selected = find(db, SUBJECT, evidence, "progress", secret)
        assert selected and selected["items"], index
        attempt = f"progress-{index:02}"
        start(
            db,
            attempt_id=attempt,
            subject=SUBJECT,
            evidence_id=evidence,
            corpus_version="progress",
            reference=selected["items"][0]["reference"],
            secret=secret,
        )
        if index == 1:
            reveal(db, attempt, SUBJECT, event_id="reveal")
        move = "b5a3" if index < 8 or index == 19 else "b5c7"
        submit(db, attempt, SUBJECT, event_id="answer", move=move)
        if index == 19:
            continue
        with monkeypatch.context() as patch:
            if index in (8, 18):
                patch.setattr(objective_fork_judge, "fork_proof", lambda *_args: None)
            process(db, SUBJECT)

    # Unrelated sessions do not consume the report's candidate window.
    original = dict(
        db.connection.execute(
            "SELECT * FROM unified_sessions WHERE attempt_id='progress-00'"
        ).fetchone()
    )
    columns = list(original)
    unrelated = {
        **original,
        "source_type": "public",
        "objective": "legal_line",
        "prompt_fen": chess.STARTING_FEN,
        "started_at": "2000-01-01T00:00:00+00:00",
    }
    db.connection.executemany(
        "INSERT INTO unified_sessions ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join("?" for _ in columns)
        + ")",
        [
            tuple(({**unrelated, "attempt_id": f"unrelated-{i}"})[column] for column in columns)
            for i in range(205)
        ],
    )
    # Repeated synthetic prompts stay out of matching, even beyond the window.
    legacy = {
        **unrelated,
        "source_type": "corpus",
        "objective": "execute_named_fork",
        "source_version": "progress",
        "provenance_json": original["provenance_json"],
    }
    start_time = datetime(2001, 1, 1, tzinfo=UTC)
    db.connection.executemany(
        "INSERT INTO unified_sessions ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join("?" for _ in columns)
        + ")",
        [
            tuple(
                (
                    {
                        **legacy,
                        "attempt_id": f"legacy-{i}",
                        "started_at": (
                            start_time + timedelta(seconds=2 if 2 <= i < 27 else i)
                        ).isoformat(),
                    }
                )[column]
                for column in columns
            )
            for i in range(181)
        ],
    )
    prior = {
        **original,
        "attempt_id": "prior-old-corpus",
        "source_version": "old-corpus",
        "prompt_fen": chess.STARTING_FEN,
        "started_at": "1999-01-01T00:00:00+00:00",
    }
    db.connection.execute(
        "INSERT INTO unified_sessions ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join("?" for _ in columns)
        + ")",
        tuple(prior[column] for column in columns),
    )
    duplicate = {**original, "attempt_id": "duplicate", "started_at": "2099-01-01T00:00:00+00:00"}
    db.connection.execute(
        "INSERT INTO unified_sessions ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join("?" for _ in columns)
        + ")",
        tuple(duplicate[column] for column in columns),
    )
    db.connection.commit()

    pending = report(db, SUBJECT, "progress")
    assert pending["group_size"] == 20 and pending["direction"] is None
    assert pending["recent"]["counts"]["pending"] == 1
    process(db, SUBJECT)
    original_source = related_fork_cache.source_for_evidence
    checks = []

    def checked_source(*args, **kwargs):
        checks.append(1)
        return original_source(*args, **kwargs)

    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    changes = db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(related_fork_cache, "source_for_evidence", checked_source)
        result = report(db, SUBJECT, "progress")
    assert len(checks) == 1
    assert result["direction"] == "higher" and result["group_size"] == 20
    assert result["window_limited"]
    assert result["earlier"]["end"] < result["recent"]["start"]
    assert result["earlier"]["assisted"] == 1
    assert result["earlier"]["counts"]["unresolved"] == 1
    assert result["recent"]["counts"]["unresolved"] == 1
    assert result["rating_start"] == 1200 and result["deviation_start"] == 0
    from chess_coach.fork_progress_bounds import direction
    from chess_coach.fork_progress_samples import sample

    unknown = sample(
        [
            {**entry, "status": "unresolved"} if not entry.get("hints") else entry
            for entry in result["earlier"]["items"]
        ]
    )
    assert direction(unknown, result["recent"]) is None
    too_few = sample(
        [
            {**entry, "hints": 1} if index < 6 else entry
            for index, entry in enumerate(result["recent"]["items"])
        ]
    )
    assert direction(result["earlier"], too_few) is None
    assert db.connection.total_changes == changes
    assert db.connection.execute("PRAGMA data_version").fetchone()[0] == version

    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="progress",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    from chess_coach.fork_attempt_page import page as attempts_page

    older_page = attempts_page(db, SUBJECT, "newer-corpus", app.secret_key, None)
    assert any(entry["older"] and entry["status"] == "correct" for entry in older_page["items"])
    base = "https://coach.invalid"
    assert client.get("/plan/forks/progress", base_url=base).status_code == 403
    page = client.get(
        "/plan/forks/progress", base_url=base, headers={"Tailscale-User-Login": "fixture-login"}
    )
    assert page.status_code == 200
    assert b"higher in the recent sample" in page.data
    assert b"/plan/forks/next" in page.data and b"/game-samples/knight-forks" in page.data
    assert b"synthetic-" not in page.data
    assert not re.search(rb"(?<![A-Za-z0-9_-])b5c7(?![A-Za-z0-9_-])", page.data)
    assert b"/plan/forks/attempts" in page.data
    assert client.get("/plan/forks/attempts", base_url=base).status_code == 403

    def next_link(response):
        match = re.search(rb'href="([^"]+)">Earlier fork assessments</a>', response.data)
        return html.unescape(match.group(1).decode()) if match else None

    headers = {"Tailscale-User-Login": "fixture-login"}
    archive = client.get("/plan/forks/attempts", base_url=base, headers=headers)
    assert archive.status_code == 200 and b"Verified" in archive.data
    link = next_link(archive)
    assert link
    cursor = parse_qs(urlsplit(link).query)["cursor"][0]
    from chess_coach.fork_attempt_cursor import unpack

    with pytest.raises(ValueError):
        unpack(app.secret_key, "other-subject", cursor)
    assert (
        client.get(
            "/plan/forks/attempts",
            query_string={"cursor": cursor + "x"},
            base_url=base,
            headers=headers,
        ).status_code
        == 400
    )
    seen = set(re.findall(rb"legacy-\d+", archive.data))
    for _ in range(15):
        archive = client.get(link, base_url=base, headers=headers)
        assert archive.status_code == 200
        seen.update(re.findall(rb"legacy-\d+", archive.data))
        if b"prior-old-corpus" in archive.data:
            assert b"old-corpus" in archive.data and b"older corpus version" in archive.data
            assert b"Unavailable or stale" in archive.data
            break
        link = next_link(archive)
        assert link
    else:
        pytest.fail("older assessment was not reachable")
    assert seen == {f"legacy-{index}".encode() for index in range(181)}

    from chess_coach import fork_attempt_read
    from chess_coach.tactical_course_budget import PreviewUnavailable

    with monkeypatch.context() as patch:
        patch.setattr(
            fork_attempt_read,
            "item",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        slow = client.get("/plan/forks/attempts", base_url=base, headers=headers)
        assert slow.status_code == 200 and b"Outcome unavailable" in slow.data
        assert b"duplicate" in slow.data
        link = next_link(slow)
        assert link
        after = parse_qs(urlsplit(link).query)["cursor"][0]
        assert unpack(app.secret_key, SUBJECT, after)[1] == "duplicate"
        assert client.get(link, base_url=base, headers=headers).status_code == 200

    import sqlite3

    from chess_coach import fork_progress_report

    def changed_source(*args, **kwargs):
        source = original_source(*args, **kwargs)
        with sqlite3.connect(path) as other:
            other.execute("UPDATE games SET event=event WHERE id=1")
        return source

    with monkeypatch.context() as patch:
        patch.setattr(related_fork_cache, "source_for_evidence", changed_source)
        changed = client.get(
            "/plan/forks/progress",
            base_url=base,
            headers={"Tailscale-User-Login": "fixture-login"},
        )
        assert changed.status_code == 200 and b"checks were incomplete" in changed.data
        assert b"higher in the recent sample" not in changed.data

    with monkeypatch.context() as patch:
        patch.setattr(
            fork_progress_report,
            "select",
            lambda *_args: (_ for _ in ()).throw(PreviewUnavailable()),
        )
        assert report(db, SUBJECT, "progress")["status"] == "incomplete"

    from chess_coach.evidence_review import review_evidence

    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    stale = report(db, SUBJECT, "progress")
    assert stale["direction"] is None
    assert stale["earlier"]["counts"]["stale"] == stale["recent"]["counts"]["stale"] == 10
    db.close()
