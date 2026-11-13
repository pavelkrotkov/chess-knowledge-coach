"""Check indexed prior sessions and imported source-game ownership."""

from .learner_identity import normalize_identity
from .related_capture_familiar import LIMIT


def sessions(db, subject, key, check):
    prefix = key + " "
    rows = db.connection.execute(
        "SELECT subject FROM unified_sessions WHERE prompt_fen>=? AND prompt_fen<? LIMIT ?",
        (prefix, prefix + "\uffff", LIMIT + 1),
    ).fetchall()
    if len(rows) > LIMIT:
        raise ValueError("recognition encounter coverage unavailable")
    identity = normalize_identity(subject)
    for item in rows:
        check()
        if normalize_identity(item["subject"]) == identity:
            return True
    return False


def source_game(db, row, check):
    if not row["source_game"]:
        return
    games = db.connection.execute(
        "SELECT white,black FROM games WHERE source='lichess' AND source_id=? LIMIT ?",
        (row["source_game"], LIMIT + 1),
    ).fetchall()
    if len(games) > LIMIT:
        raise ValueError("recognition source game coverage unavailable")
    for game in games:
        check()
        if row["subject"] in {normalize_identity(game["white"]), normalize_identity(game["black"])}:
            raise ValueError("recognition source game is familiar")
