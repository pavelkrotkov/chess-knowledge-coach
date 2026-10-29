"""Independent rotating cursor for automatic mate observations."""

from .deep_selection_source import learner_key
from .fact_fingerprint import digest

POLICY = "mate-auto-v1"


def scan(db, learner, limit):
    key = digest("mate-worker-cursor-v1:" + learner_key(learner))
    row = db.connection.execute(
        "SELECT last_game_id,scan_hash FROM pipeline_cursors WHERE account_key=?", (key,)
    ).fetchone()
    cursor = row[0] if row and row[1] == POLICY else 0
    rows = db.connection.execute(
        "SELECT id FROM positions WHERE id>? ORDER BY id LIMIT ?", (cursor, limit + 1)
    ).fetchall()
    if not rows and cursor:
        rows = db.connection.execute(
            "SELECT id FROM positions ORDER BY id LIMIT ?", (limit + 1,)
        ).fetchall()
    return key, rows
