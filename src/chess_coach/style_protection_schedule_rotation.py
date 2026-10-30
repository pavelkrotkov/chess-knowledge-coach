"""Fair protection-target rotation independent of check and control slots."""

from .style_schedule_candidates_rank import rank


def choose(db, key, candidates):
    games = {}
    for item in candidates:
        games.setdefault(item["game_id"], []).append(item)
    if not games:
        return None
    indexes = {game: _index(db, key, game) for game in games}
    game = min(games, key=lambda value: (indexes[value], rank(key, "protection", value, 0)))
    items = sorted(games[game], key=lambda item: rank(key, "protection", game, item["position_id"]))
    return items[indexes[game] % len(items)]


def _index(db, key, game):
    row = db.connection.execute(
        "SELECT next_index FROM style_protection_rotation WHERE learner_key=? AND game_id=?",
        (key, game),
    ).fetchone()
    return row[0] if row else 0


def advance(db, key, game):
    if game is None:
        return
    db.connection.execute(
        """INSERT INTO style_protection_rotation(learner_key,game_id,next_index) VALUES(?,?,1)
        ON CONFLICT(learner_key,game_id) DO UPDATE SET next_index=next_index+1""",
        (key, game),
    )
