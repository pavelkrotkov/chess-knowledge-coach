"""Durably admit and record one uncued first encounter."""

import json
import sqlite3
from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .recognition_candidates import choose
from .recognition_current import source


def _now():
    return datetime.now(UTC).isoformat()


def row(db, subject, attempt):
    item = db.connection.execute(
        """SELECT a.*,e.action,e.answer,e.assisted,e.created_at AS answered_at
        FROM recognition_attempts a LEFT JOIN recognition_events e ON e.attempt_id=a.attempt_id
        WHERE a.subject=? AND a.attempt_id=?""",
        (normalize_identity(subject), attempt),
    ).fetchone()
    if item is None:
        raise ValueError("recognition attempt unavailable")
    return item


def recent(db, subject):
    return db.connection.execute(
        """SELECT a.attempt_id,e.action FROM recognition_attempts a LEFT JOIN recognition_events e
        ON e.attempt_id=a.attempt_id WHERE a.subject=?
        ORDER BY a.started_at DESC,a.attempt_id DESC LIMIT 10""",
        (normalize_identity(subject),),
    ).fetchall()


def start(db, subject, version, attempt):
    candidate, data_version = choose(db, subject, version)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != data_version:
            raise ValueError("recognition source changed")
        db.connection.execute(
            """INSERT INTO recognition_attempts
            (attempt_id,subject,prompt_key,prompt_fen,learner_color,source_version,source_key,
             source_url,source_game,source_fingerprint,proof_json,content_rating,content_deviation,content_opening,cue_status,started_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                attempt,
                normalize_identity(subject),
                candidate["prompt_key"],
                candidate["prompt_fen"],
                candidate["learner_color"],
                candidate["source_version"],
                candidate["source_key"],
                candidate["source_url"],
                candidate["source_game"],
                candidate["source_fingerprint"],
                json.dumps(candidate["proof"], sort_keys=True),
                candidate["rating"],
                candidate["deviation"],
                candidate["opening"],
                "uncued",
                _now(),
            ),
        )
        saved = row(db, subject, attempt)
        source(db, saved)
        db.connection.commit()
    except sqlite3.IntegrityError:
        db.connection.rollback()
        raise ValueError("recognition prompt already encountered") from None
    except BaseException:
        db.connection.rollback()
        raise
    return attempt
