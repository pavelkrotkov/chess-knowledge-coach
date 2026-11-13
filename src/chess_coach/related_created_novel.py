"""Recheck post-admission familiarity before the first legal answer."""

import sqlite3
import time

from .learner_identity import normalize_identity
from .puzzle_session_validate import validate_line
from .recognition_game_frontier import MAX_NEW_GAMES, new_initials
from .related_capture_position import prompt_key
from .related_protection_assessment_novelty import _check as check_protection


def require_created_novel(db, row, binding):
    until = time.monotonic() + 2

    def check():
        if time.monotonic() >= until:
            raise ValueError("familiarity check timed out")

    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        # Share one deadline across indexed, legacy and newly imported-game checks.
        check_protection(db, row, until)
        new_initials(
            db,
            {
                "game_watermark": binding["game_watermark"],
                "subject": normalize_identity(row["subject"]),
                "prompt_key": prompt_key(row["prompt_fen"]),
            },
            check,
        )
        _legacy_since(db, binding["legacy_watermark"], prompt_key(row["prompt_fen"]), check)
        identity = normalize_identity(row["subject"])
        if db.connection.execute(
            "SELECT 1 FROM recognition_attempts WHERE subject=? AND prompt_key=? LIMIT 1",
            (identity, prompt_key(row["prompt_fen"])),
        ).fetchone():
            raise ValueError("practice prompt became familiar")
        game = binding.get("source_game")
        if (
            game
            and db.connection.execute(
                "SELECT 1 FROM games WHERE source_id=? AND (lower(white)=? OR lower(black)=?) LIMIT 1",
                (game, normalize_identity(row["subject"]), normalize_identity(row["subject"])),
            ).fetchone()
        ):
            raise ValueError("practice source became familiar")
        check()
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("familiarity check timed out") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)


def _legacy_since(db, watermark, key, check):
    if type(watermark) is not int or watermark < 0:
        raise ValueError("legacy familiarity frontier unavailable")
    rows = db.connection.execute(
        "SELECT initial_fen,solution FROM puzzle_sessions WHERE rowid>? ORDER BY rowid LIMIT ?",
        (watermark, MAX_NEW_GAMES + 1),
    ).fetchall()
    if len(rows) > MAX_NEW_GAMES:
        raise ValueError("legacy familiarity coverage unavailable")
    for item in rows:
        check()
        if prompt_key(validate_line(item["initial_fen"], item["solution"])) == key:
            raise ValueError("practice prompt became familiar")
