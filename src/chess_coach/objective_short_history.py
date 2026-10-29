"""Validate later assistance and illegal events against resumed history."""

from .fact_fingerprint import canonical, digest
from .objective_events import prefix, response


def validate_later_events(db, session, event_id, board):
    events = prefix(db, session["attempt_id"], event_id)
    target = db.connection.execute(
        "SELECT rowid FROM unified_session_events WHERE attempt_id=? AND event_id=?",
        (session["attempt_id"], event_id),
    ).fetchone()[0]
    rows = db.connection.execute(
        "SELECT kind,response_json FROM unified_session_events WHERE attempt_id=? AND rowid>? ORDER BY rowid LIMIT 257",
        (session["attempt_id"], target),
    ).fetchall()
    if len(events) + len(rows) > 256:
        raise ValueError("continuation history exceeds limit")
    for row in rows:
        detail = response(row)
        if (row["kind"] != "hint" and detail.get("feedback") != "illegal") or detail.get(
            "fen"
        ) != board.fen():
            raise ValueError("continuation history changed")


def append_reply(db, attempt, subject, steps):
    from .objective_short_continue import continuation
    from .unified_session_state import session_row

    resumed = continuation(db, session_row(db, attempt, subject))
    if resumed and not resumed["complete"]:
        steps.append({"fen": resumed["board"].fen(), "label": "Reply: " + resumed["defense"]})
    return steps


def history_hash(board):
    return digest(
        canonical(
            {
                "root": board.root().fen(en_passant="fen", promoted=True),
                "moves": [move.uci() for move in board.move_stack],
            }
        )
    )
