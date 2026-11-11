"""Compare certified fork attempts without modifying learning state."""

import re
from datetime import UTC, datetime, timedelta

import chess

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
    # Older sessions without frozen context stay out of matching, even beyond the window.
    legacy = {
        **unrelated,
        "source_type": "corpus",
        "objective": "execute_named_fork",
        "source_version": "progress",
        "provenance_json": "{}",
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
                        "started_at": (start_time + timedelta(seconds=i)).isoformat(),
                    }
                )[column]
                for column in columns
            )
            for i in range(181)
        ],
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
    import sqlite3

    from chess_coach import fork_progress_report
    from chess_coach.tactical_course_budget import PreviewUnavailable

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
