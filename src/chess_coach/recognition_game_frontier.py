"""Recheck initial boards of learner games imported after admission."""

from .related_capture_familiar import _initial_prompt

MAX_NEW_GAMES = 1000


def new_initials(db, row, check):
    watermark = row["game_watermark"]
    if type(watermark) is not int or watermark < 0:
        raise ValueError("recognition game frontier unavailable")
    games = db.connection.execute(
        """SELECT pgn FROM games WHERE id>? AND (lower(white)=? OR lower(black)=?)
        ORDER BY id LIMIT ?""",
        (watermark, row["subject"], row["subject"], MAX_NEW_GAMES + 1),
    ).fetchall()
    if len(games) > MAX_NEW_GAMES:
        raise ValueError("recognition imported-game coverage unavailable")
    for game in games:
        check()
        if _initial_prompt(game["pgn"]) == row["prompt_key"]:
            raise ValueError("recognition prompt became familiar")
