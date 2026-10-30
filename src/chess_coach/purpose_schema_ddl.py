"""Exact schema objects for isolated purpose-analysis persistence."""

Q = chr(39)
STATEMENTS = {
    "purpose_analysis_requests": (
        "CREATE TABLE purpose_analysis_requests (id INTEGER PRIMARY KEY, "
        "game_id INTEGER NOT NULL REFERENCES games(id), position_id INTEGER NOT NULL REFERENCES positions(id), "
        "learner_key TEXT NOT NULL, purpose TEXT NOT NULL, policy_version TEXT NOT NULL, "
        "cheap_run_id INTEGER NOT NULL REFERENCES analysis_runs(id), source_fingerprint TEXT NOT NULL, "
        "config_json TEXT NOT NULL CHECK(json_valid(config_json)), request_fingerprint TEXT NOT NULL UNIQUE, "
        f"status TEXT NOT NULL CHECK(status IN ({Q}pending{Q},{Q}running{Q},{Q}complete{Q},"
        f"{Q}insufficient{Q},{Q}stale{Q},{Q}interrupted{Q})), "
        "attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 2), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    ),
    "purpose_analysis_attempts": (
        "CREATE TABLE purpose_analysis_attempts (id INTEGER PRIMARY KEY, "
        "request_id INTEGER NOT NULL REFERENCES purpose_analysis_requests(id), "
        "attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 2), "
        f"status TEXT NOT NULL CHECK(status IN ({Q}complete{Q},{Q}insufficient{Q},"
        f"{Q}stale{Q},{Q}interrupted{Q})), detail TEXT NOT NULL, "
        "result_json TEXT NOT NULL CHECK(json_valid(result_json)), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(request_id,attempt_number))"
    ),
    "idx_purpose_requests_owner": (
        "CREATE INDEX idx_purpose_requests_owner ON purpose_analysis_requests(learner_key,id)"
    ),
    "purpose_attempts_no_update": (
        "CREATE TRIGGER purpose_attempts_no_update BEFORE UPDATE ON purpose_analysis_attempts "
        f"BEGIN SELECT RAISE(ABORT,{Q}purpose attempts are immutable{Q}); END"
    ),
    "purpose_attempts_no_delete": (
        "CREATE TRIGGER purpose_attempts_no_delete BEFORE DELETE ON purpose_analysis_attempts "
        f"BEGIN SELECT RAISE(ABORT,{Q}purpose attempts are immutable{Q}); END"
    ),
    "purpose_request_identity_immutable": (
        "CREATE TRIGGER purpose_request_identity_immutable BEFORE UPDATE OF "
        "game_id,position_id,learner_key,purpose,policy_version,cheap_run_id,source_fingerprint,"
        "config_json,request_fingerprint,created_at ON purpose_analysis_requests "
        f"BEGIN SELECT RAISE(ABORT,{Q}purpose request identity is immutable{Q}); END"
    ),
    "purpose_request_no_delete": (
        "CREATE TRIGGER purpose_request_no_delete BEFORE DELETE ON purpose_analysis_requests "
        f"BEGIN SELECT RAISE(ABORT,{Q}purpose requests are immutable{Q}); END"
    ),
}
