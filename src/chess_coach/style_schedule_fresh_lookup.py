"""Find bounded prior candidates by indexed game context."""

from .style_time_projection import VERSION

MAX_ALIASES = 32


def contexts(db, identities):
    marks = ",".join("?" for _ in identities)
    rows = db.connection.execute(
        f"""SELECT game_id,started_at,white_identity,black_identity FROM style_game_times
        WHERE game_id IN ({marks}) AND status='current' AND version=?""",
        (*identities, VERSION),
    ).fetchall()
    contexts = {}
    for row in rows:
        contexts.setdefault(tuple(row[1:]), set()).add(identities[row[0]])
    missing = set(identities) - {row[0] for row in rows}
    return contexts, {identities[game] for game in missing}


def aliases(db, context):
    started, white, black = context
    rows = db.connection.execute(
        """SELECT game_id FROM style_game_times INDEXED BY idx_style_time_white
        WHERE status='current' AND version=? AND white_identity=? AND started_at=?
          AND black_identity=? LIMIT ?""",
        (VERSION, white, started, black, MAX_ALIASES + 1),
    ).fetchall()
    return [row[0] for row in rows]


def prior(db, key, games):
    marks = ",".join("?" for _ in games)
    return [
        row[0]
        for row in db.connection.execute(
            f"""SELECT DISTINCT s.game_id FROM style_schedule_cycles c
            JOIN style_schedule_slots s ON s.cycle_id=c.id
            WHERE c.learner_key=? AND s.kind='control' AND c.sequence % 4=1
              AND s.game_id IN ({marks})
              AND json_extract(c.coverage_json,'$.early_center_policy')='early-center-v1'
              AND json_extract(c.coverage_json,'$.early_center_targeted')=1
              AND (s.request_id IS NOT NULL OR s.status IN ('ready','pending','running','interrupted'))""",
            (key, *games),
        )
    ]
