"""Look up immutable completion records through their direct foreign keys."""

from .db import Database


def completion_source(db: Database, evidence_id: int):
    return db.connection.execute(
        """SELECT c.attempt_id, c.policy_version, c.mapper_version, c.evidence_reason, c.request_hash,
        c.created_at, s.corpus_version, s.puzzle_id, s.initial_fen, s.solution,
        s.current_fen, s.status, s.hints_used, s.finished_at,
        t.reviewed_at, i.id AS item_id, i.source_type, i.source_ref, i.skill, i.operation,
        ev.event_id, ev.kind AS event_kind, ev.submitted_move, ev.created_at AS event_time,
        (SELECT COUNT(*) FROM puzzle_session_events h
         WHERE h.attempt_id=s.attempt_id AND h.kind=?) AS hint_events
        FROM training_completions c
        JOIN puzzle_sessions s ON s.attempt_id=c.attempt_id
        JOIN training_attempts t ON t.id=c.training_attempt_id
        JOIN training_items i ON i.id=t.item_id
        LEFT JOIN puzzle_session_events ev ON ev.rowid=(
            SELECT MAX(rowid) FROM puzzle_session_events WHERE attempt_id=s.attempt_id
        )
        WHERE c.evidence_id=?""",
        ("hint", evidence_id),
    ).fetchone()
