"""Keep diagnostic task snapshots and events separate from move practice."""


def add_probes(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS diagnostic_probes (
        attempt_id TEXT PRIMARY KEY, subject TEXT NOT NULL,
        lesson_id INTEGER NOT NULL REFERENCES lesson_versions(id),
        evidence_id INTEGER NOT NULL REFERENCES evidence_mappings(id),
        position_id INTEGER NOT NULL REFERENCES positions(id),
        task_json TEXT NOT NULL, source_hash TEXT NOT NULL, started_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS diagnostic_probe_events (
        attempt_id TEXT NOT NULL REFERENCES diagnostic_probes(attempt_id),
        event_id TEXT NOT NULL, kind TEXT NOT NULL, request_json TEXT NOT NULL,
        response_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (attempt_id, event_id))""")
    for table in ("diagnostic_probes", "diagnostic_probe_events"):
        for action in ("UPDATE", "DELETE"):
            connection.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()}
                BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT, 'probe history is immutable'); END""")
