"""Append and retrieve private immutable lesson versions."""

import json

from .learner_identity import normalize_identity


def save(
    db, learner, lesson, *, model="deterministic", prompt_version="coach-lesson-v1", inputs=None
):
    subject = normalize_identity(learner)
    if not subject:
        raise ValueError("lesson subject unavailable")
    body = json.dumps(lesson, sort_keys=True, allow_nan=False)
    provenance = json.dumps(inputs or {}, sort_keys=True, allow_nan=False)
    row = db.connection.execute(
        """INSERT INTO lesson_versions(subject, lesson_json, generator_model, prompt_version, input_json)
        VALUES (?, ?, ?, ?, ?)""",
        (subject, body, model, prompt_version, provenance),
    )
    return row.lastrowid


def get(db, learner, lesson_id):
    subject = normalize_identity(learner)
    row = db.connection.execute(
        "SELECT * FROM lesson_versions WHERE id=? AND subject=?", (lesson_id, subject)
    ).fetchone()
    if row is None:
        raise ValueError("lesson unavailable")
    return {
        **dict(row),
        "lesson": json.loads(row["lesson_json"]),
        "inputs": json.loads(row["input_json"]),
    }


def list_versions(db, learner, before):
    if not 0 < before <= 2**63 - 1:
        raise ValueError("invalid history cursor")
    rows = db.connection.execute(
        "SELECT id, lesson_json, generated_at FROM lesson_versions WHERE subject=? AND id<? ORDER BY id DESC LIMIT 101",
        (normalize_identity(learner), before),
    ).fetchall()
    items = []
    for row in rows[:100]:
        lesson = json.loads(row["lesson_json"])
        items.append(
            {
                "id": row["id"],
                "generated_at": row["generated_at"],
                "skill": lesson["skill"],
                "operation": lesson["operation"],
            }
        )
    return items, items[-1]["id"] if len(rows) > 100 else None
