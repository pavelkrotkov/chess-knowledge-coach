"""Read bounded games and collapse indistinguishable game records."""

from collections import Counter

from .mastery_game_lookup import decisions_for_game
from .repertoire_game import _outcome

MAX_POSITIONS = 1000


def _contexts(db, game, learner):
    count = db.connection.execute(
        "SELECT COUNT(*) FROM positions WHERE game_id=?", (game["id"],)
    ).fetchone()[0]
    if count > MAX_POSITIONS:
        return None
    verified = decisions_for_game(db, game["id"], learner)
    if verified is None:
        return None
    return [item for item in verified.values() if item["subject"]]


def collect_games(db, games, learner):
    rows, contexts, outcomes, seen = [], [], Counter(), set()
    skipped = duplicates = 0
    for game, color in games:
        items = _contexts(db, game, learner)
        if not items:
            skipped += 1
            continue
        identity = items[0]["game_key"]
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        outcome = _outcome(game["result"], color)
        outcomes[outcome] += 1
        for item in items:
            item["game_outcome"] = outcome
        contexts.extend(items)
        rows.append({"game_id": game["id"], "contexts": items})
    return rows, contexts, dict(outcomes), skipped, duplicates
