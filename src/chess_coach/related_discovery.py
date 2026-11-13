"""Bounded source-related discovered-mate selection and admission."""

import sqlite3
import time

from .related_capture_familiar import familiarity
from .related_discovery_contract import VERSION
from .related_discovery_match import candidate
from .related_discovery_source import source_for_evidence
from .related_transfer_select import select

SECONDS = 12


def selection(db, subject, evidence_id, corpus):
    deadline = time.monotonic() + SECONDS

    def check():
        if time.monotonic() >= deadline:
            raise ValueError("discovered mate search timed out")

    generation = db.connection.execute("PRAGMA data_version").fetchone()[0]
    frontier = db.connection.execute(
        """SELECT (SELECT COALESCE(MAX(id), 0) FROM games),
        (SELECT COALESCE(MAX(rowid), 0) FROM puzzle_sessions)"""
    ).fetchone()
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        source = source_for_evidence(db, subject, evidence_id)
        familiar = familiarity(db, subject, check=check)

        def score(item, features, seen, rating):
            check()
            return candidate(item, features, seen, rating)

        chosen = select(
            db,
            subject,
            source,
            corpus,
            VERSION,
            theme="discoveredAttack",
            all_lines=True,
            include_objective=True,
            familiar_data=familiar,
            feature=lambda _fen, _line: dict(source["features"]),
            score=score,
        )
        check()
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != generation:
            raise ValueError("discovered mate search changed")
        if chosen is not None:
            chosen[2]["frontier"] = tuple(frontier)
        return chosen
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("discovered mate search timed out") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)


def error_message(error, fallback):
    return {
        "discovered mate search timed out": "This search timed out. Please try again.",
        "discovered mate search changed": "This search changed. Please try again.",
    }.get(str(error), fallback)
