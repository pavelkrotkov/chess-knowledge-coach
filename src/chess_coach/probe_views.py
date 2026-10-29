"""Load owned probes and expose only public task state."""

import json

from .probe_design import design


def checked_row(db, subject, attempt_id):
    row = _owned_row(db, subject, attempt_id)
    saved = json.loads(row["task_json"])
    task, fingerprint, position = design(
        db, subject, row["lesson_id"], row["evidence_id"], saved["operation"]
    )
    if task != saved or fingerprint != row["source_hash"] or position != row["position_id"]:
        raise ValueError("probe source is stale")
    return row, saved


def show(db, subject, attempt_id):
    row = _owned_row(db, subject, attempt_id)
    try:
        _, task = checked_row(db, subject, attempt_id)
        stale = False
    except ValueError:
        task = json.loads(row["task_json"])
        stale = True
    events = db.connection.execute(
        "SELECT kind,response_json FROM diagnostic_probe_events WHERE attempt_id=? ORDER BY rowid",
        (attempt_id,),
    ).fetchall()
    return {
        "attempt_id": attempt_id,
        "lesson_id": row["lesson_id"],
        "stale": stale,
        **{k: task[k] for k in ("operation", "fen", "question", "familiarity")},
        "events": [json.loads(event["response_json"]) for event in events],
        "answered": any(event["kind"] == "answer" for event in events),
    }


def _owned_row(db, subject, attempt_id):
    row = db.connection.execute(
        "SELECT * FROM diagnostic_probes WHERE attempt_id=? AND subject=?", (attempt_id, subject)
    ).fetchone()
    if not row:
        raise ValueError("unknown probe")
    return row
