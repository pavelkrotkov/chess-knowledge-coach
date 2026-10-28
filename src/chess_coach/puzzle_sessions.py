"""Start and resume verified, versioned puzzle attempts."""

from __future__ import annotations

from .db import Database
from .puzzle_session_events import request_hint as request_hint
from .puzzle_session_events import submit_move as submit_move
from .puzzle_session_state import _now, _session, _view
from .puzzle_session_state import show_attempt as show_attempt
from .puzzle_session_validate import validate_line


def start_attempt(
    db: Database, *, attempt_id: str, version: str, puzzle_id: str
) -> dict[str, object]:
    if not attempt_id or not version or not puzzle_id:
        raise ValueError("attempt ID, corpus version, and puzzle ID are required")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start an attempt during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        existing = db.connection.execute(
            "SELECT * FROM puzzle_sessions WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if existing is not None:
            if (existing["corpus_version"], existing["puzzle_id"]) != (version, puzzle_id):
                raise ValueError("attempt ID already belongs to another puzzle")
            result = _view(existing)
        else:
            result = _create_attempt(db, attempt_id, version, puzzle_id)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _create_attempt(
    db: Database, attempt_id: str, version: str, puzzle_id: str
) -> dict[str, object]:
    puzzle = db.connection.execute(
        """SELECT puzzles.fen, puzzles.solution, puzzle_corpora.checksum
        FROM puzzles JOIN puzzle_corpora ON puzzles.corpus_id = puzzle_corpora.id
        WHERE puzzle_corpora.version = ? AND puzzles.puzzle_id = ?""",
        (version, puzzle_id),
    ).fetchone()
    if puzzle is None:
        raise ValueError("unknown versioned puzzle")
    fen = validate_line(puzzle["fen"], puzzle["solution"])
    db.connection.execute(
        """INSERT INTO puzzle_sessions
        (attempt_id, corpus_version, corpus_checksum, puzzle_id, initial_fen, solution,
         current_fen, next_index, status, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'active', ?)""",
        (
            attempt_id,
            version,
            puzzle["checksum"],
            puzzle_id,
            puzzle["fen"],
            puzzle["solution"],
            fen,
            _now(),
        ),
    )
    return _view(_session(db, attempt_id))
