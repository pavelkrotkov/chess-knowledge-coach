"""Recheck one first-encounter result and its matching context."""

import json

import chess

from .mastery_time import parse_utc
from .protection_followup_context import context
from .protection_plan_verify import inspect


def _time(value):
    parsed = parse_utc(value)
    if parsed is None or parsed.isoformat() != value:
        raise ValueError("assessment time unavailable")
    return parsed


def _answer(db, row):
    events = db.connection.execute(
        """SELECT e.created_at FROM objective_requests q
        JOIN unified_session_events e ON e.attempt_id=q.attempt_id AND e.event_id=q.event_id
        WHERE q.attempt_id=? ORDER BY q.rowid LIMIT 2""",
        (row["attempt_id"],),
    ).fetchall()
    if len(events) != 1 or _time(events[0]["created_at"]) < _time(row["started_at"]):
        raise ValueError("assessment time unavailable")
    return events[0]["created_at"]


def _metadata(db, row, corpus):
    meta = db.connection.execute(
        """SELECT p.rating_deviation,c.checksum FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (corpus, row["source_key"]),
    ).fetchone()
    if meta is None or not isinstance(meta["checksum"], str) or not meta["checksum"]:
        raise ValueError("assessment context unavailable")
    deviation = meta["rating_deviation"]
    if deviation is not None and (type(deviation) is not int or not 0 <= deviation < 4000):
        raise ValueError("assessment context unavailable")
    return meta["checksum"], None if deviation is None else deviation // 100


def _scope(db, row, corpus, binding):
    move = binding["assessment"]["proof"]["move"]
    mover, target, mechanism, rating = context(
        db, corpus, row["source_key"], binding, row["prompt_fen"], move
    )
    checksum, deviation = _metadata(db, row, corpus)
    board = chess.Board(row["prompt_fen"])
    if row["learner_color"] != ("white" if board.turn else "black"):
        raise ValueError("assessment side unavailable")
    return (corpus, checksum, row["learner_color"], mover, target, mechanism, rating, deviation)


def item(db, row, corpus, check):
    binding = json.loads(row["provenance_json"])["related_protection"]
    evidence = binding["evidence_id"]
    # Replaying the complete attempt also catches hints given after verification.
    result = inspect(db, row, corpus, evidence)
    check()
    if result["status"] not in ("correct", "incorrect"):
        raise ValueError("assessment result unresolved")
    return {
        "attempt": row["attempt_id"],
        "started_at": row["started_at"],
        "answered_at": _answer(db, row),
        "status": result["status"],
        "scope": _scope(db, row, corpus, binding),
        "current": True,
        "hints": 0,
        "outcome": "verified" if result["status"] == "correct" else "incorrect",
    }
