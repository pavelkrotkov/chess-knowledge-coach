"""Keep objective-verification requests and results as immutable history."""


def add_objective_verification(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS objective_requests (
        attempt_id TEXT NOT NULL, event_id TEXT NOT NULL, subject TEXT NOT NULL,
        objective_version TEXT NOT NULL, history_mode TEXT NOT NULL,
        snapshot_hash TEXT NOT NULL, source_hash TEXT NOT NULL,
        event_prefix_hash TEXT NOT NULL, learner_color TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        PRIMARY KEY (attempt_id, event_id),
        FOREIGN KEY (attempt_id, event_id) REFERENCES unified_session_events(attempt_id, event_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS objective_results (
        attempt_id TEXT NOT NULL, event_id TEXT NOT NULL,
        result_json TEXT NOT NULL, completed_at TEXT NOT NULL,
        PRIMARY KEY (attempt_id, event_id),
        FOREIGN KEY (attempt_id, event_id) REFERENCES objective_requests(attempt_id, event_id)
    )""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_objective_requests_subject ON objective_requests(subject, requested_at, attempt_id, event_id)"
    )
    for table in ("objective_requests", "objective_results"):
        for action in ("UPDATE", "DELETE"):
            connection.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()}
                BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT, \u0027objective history is immutable\u0027); END""")
