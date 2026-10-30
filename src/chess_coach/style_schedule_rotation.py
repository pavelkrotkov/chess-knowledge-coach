"""Rotate each game's candidate slots independently of the game scan."""

from .style_schedule_candidates_rank import rank


def choose(db, key, kind, candidates):
    games = {}
    for item in candidates:
        games.setdefault(item["game_id"], []).append(item)
    if not games:
        return None
    indexes = {game_id: _index(db, key, kind, game_id) for game_id in games}
    game_id = min(games, key=lambda game: (indexes[game], rank(key, kind, game, 0)))
    items = sorted(games[game_id], key=lambda item: rank(key, kind, game_id, item["position_id"]))
    return items[indexes[game_id] % len(items)]


def _index(db, key, kind, game_id):
    row = db.connection.execute(
        "SELECT next_index FROM style_schedule_rotation WHERE learner_key=? AND game_id=? AND kind=?",
        (key, game_id, kind),
    ).fetchone()
    return row[0] if row is not None else 0


def advance(db, key, kind, game_id):
    if game_id is None:
        return
    db.connection.execute(
        """INSERT INTO style_schedule_rotation(learner_key,game_id,kind,next_index) VALUES(?,?,?,1)
        ON CONFLICT(learner_key,game_id,kind) DO UPDATE SET next_index=next_index+1""",
        (key, game_id, kind),
    )
