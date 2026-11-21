"""Durable enrollment and completion for qualified unified practice."""


def add_unified_training(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS unified_training_enrollments (
        attempt_id TEXT PRIMARY KEY REFERENCES unified_sessions(attempt_id),
        item_id INTEGER NOT NULL REFERENCES training_items(id),
        subject TEXT NOT NULL, created_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS unified_training_completions (
        attempt_id TEXT PRIMARY KEY REFERENCES unified_training_enrollments(attempt_id),
        event_id TEXT NOT NULL, evidence_id INTEGER UNIQUE REFERENCES evidence_mappings(id),
        training_attempt_id INTEGER UNIQUE REFERENCES training_attempts(id),
        policy_version TEXT NOT NULL, mapper_version TEXT NOT NULL,
        outcome TEXT NOT NULL, assistance TEXT NOT NULL, reason TEXT NOT NULL,
        request_hash TEXT NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY(attempt_id,event_id) REFERENCES unified_session_events(attempt_id,event_id))""")
    for table in ("unified_training_enrollments", "unified_training_completions"):
        for action in ("UPDATE", "DELETE"):
            connection.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()}
                BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT, 'unified training history is immutable'); END""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_unified_due
        ON training_items(julianday(due),id) WHERE source_type IN ('puzzle','unified_corpus_m1')
        AND skill='mate_in_one' AND operation='execute' AND lower(due) != 'now'""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_curriculum_unified_scheduled
        ON training_items(id) WHERE source_type IN ('puzzle','unified_corpus_m1')
        AND skill='mate_in_one' AND operation='execute'""")
    for table in ("unified_training_enrollments", "unified_training_completions"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS curriculum_revision_{table}_insert AFTER INSERT ON {table}
            BEGIN UPDATE curriculum_source_revision SET revision=revision+1 WHERE id=1; END""")

    connection.execute("""CREATE TRIGGER IF NOT EXISTS unified_completed_training_attempt_no_update
        BEFORE UPDATE ON training_attempts WHEN EXISTS
        (SELECT 1 FROM unified_training_completions WHERE training_attempt_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'completed training attempts are immutable'); END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS unified_completed_session_no_update
        BEFORE UPDATE ON unified_sessions WHEN EXISTS
        (SELECT 1 FROM unified_training_completions WHERE attempt_id=OLD.attempt_id)
        BEGIN SELECT RAISE(ABORT, 'completed unified attempts are immutable'); END""")
