"""Find attributable structure games and safely expose source positions."""

from .learner_identity import learner_color, normalize_identity

MAX_GAMES = 100
MAX_SCAN = 1000


def attributable_games(db, learner):
    if normalize_identity(learner) is None:
        raise ValueError("learner identity is unavailable")
    rows = db.connection.execute(
        """SELECT g.* FROM games g JOIN structure_runs r ON r.game_id=g.id
        WHERE r.status=? ORDER BY g.id DESC LIMIT ?""",
        ("active", MAX_SCAN + 1),
    )
    games = []
    scanned = 0
    for row in rows:
        scanned += 1
        if scanned > MAX_SCAN:
            break
        color = learner_color(row, learner)
        if color:
            games.append((row["id"], color))
            if len(games) > MAX_GAMES:
                break
    return games, scanned > MAX_SCAN


def source_position(db, learner, position_id):
    row = db.connection.execute(
        """SELECT p.id,p.game_id,p.ply,p.fen,g.white,g.black,g.pgn
        FROM positions p JOIN games g ON g.id=p.game_id WHERE p.id=?""",
        (position_id,),
    ).fetchone()
    if row is None or learner_color(row, learner) is None:
        raise ValueError("position is unavailable")
    return {key: row[key] for key in ("id", "game_id", "ply", "fen")}
