"""Match game and qualified-opportunity color, control and phase contexts."""

import json
from collections import Counter


# Match the joint distribution of color, control and phase, not separate marginals.
# Missing ownership or an unsupported phase withholds the comparison.
def _counts(games, values):
    all_games, opportunities = Counter(), Counter()
    for game in games:
        value = values.get(game["id"])
        if value is None:
            return None, None
        control, color = value
        all_games[(color, control)] += 1
        for _, outcome, context in game["results"]:
            if outcome in {"protected", "missed", "opportunity_unresolved"}:
                side, phase, _reason = json.loads(context)
                if side != color or phase not in {"middlegame", "endgame"}:
                    return None, None
                opportunities[(color, control, phase)] += 1
    return all_games, opportunities


def _same(left, right):
    if not left or not right:
        return False
    return all(
        left.get(key, 0) * sum(right.values()) == right.get(key, 0) * sum(left.values())
        for key in left.keys() | right.keys()
    )


def _values(db, learner, ids):
    placeholders = ",".join("?" for _ in ids)
    rows = db.connection.execute(
        f"""SELECT g.id,g.time_control,t.white_identity,t.black_identity
        FROM games g JOIN style_game_times t ON t.game_id=g.id WHERE g.id IN ({placeholders})""",
        ids,
    ).fetchall()
    values = {}
    for row in rows:
        sides = [side for side in ("white", "black") if row[f"{side}_identity"] == learner]
        if len(sides) == 1 and isinstance(row["time_control"], str):
            values[row["id"]] = (row["time_control"], sides[0])
    return values


def matched(db, learner, games):
    ids = [game["id"] for game in games[:40]]
    if len(ids) != 40:
        return False
    values = _values(db, learner, ids)
    newer, newer_opportunities = _counts(games[:20], values)
    earlier, earlier_opportunities = _counts(games[20:40], values)
    return bool(
        newer is not None
        and earlier is not None
        and _same(newer, earlier)
        and _same(newer_opportunities, earlier_opportunities)
    )
