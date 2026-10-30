"""Durable allocation for recent-game purpose scheduling."""

STATEMENTS = {
    "style_schedule_cycles": (
        "CREATE TABLE style_schedule_cycles (id INTEGER PRIMARY KEY, learner_key TEXT NOT NULL, "
        "sequence INTEGER NOT NULL, coverage_json TEXT NOT NULL CHECK(json_valid(coverage_json)), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(learner_key,sequence))"
    ),
    "style_schedule_slots": (
        "CREATE TABLE style_schedule_slots (id INTEGER PRIMARY KEY, cycle_id INTEGER NOT NULL "
        "REFERENCES style_schedule_cycles(id), kind TEXT NOT NULL CHECK(kind IN ('target','control')), "
        "game_id INTEGER REFERENCES games(id), position_id INTEGER REFERENCES positions(id), "
        "status TEXT NOT NULL, detail TEXT NOT NULL, request_id INTEGER REFERENCES purpose_analysis_requests(id), "
        "UNIQUE(cycle_id,kind), UNIQUE(cycle_id,game_id))"
    ),
    "idx_style_schedule_owner": (
        "CREATE INDEX idx_style_schedule_owner ON style_schedule_cycles(learner_key,sequence)"
    ),
    "style_schedule_cycle_no_update": (
        "CREATE TRIGGER style_schedule_cycle_no_update BEFORE UPDATE ON style_schedule_cycles "
        "BEGIN SELECT RAISE(ABORT,'schedule cycle is immutable'); END"
    ),
    "style_schedule_cycle_no_delete": (
        "CREATE TRIGGER style_schedule_cycle_no_delete BEFORE DELETE ON style_schedule_cycles "
        "BEGIN SELECT RAISE(ABORT,'schedule cycle is immutable'); END"
    ),
    "style_schedule_slot_identity": (
        "CREATE TRIGGER style_schedule_slot_identity BEFORE UPDATE OF cycle_id,kind,game_id,position_id "
        "ON style_schedule_slots BEGIN SELECT RAISE(ABORT,'schedule allocation is immutable'); END"
    ),
    "style_schedule_slot_no_delete": (
        "CREATE TRIGGER style_schedule_slot_no_delete BEFORE DELETE ON style_schedule_slots "
        "BEGIN SELECT RAISE(ABORT,'schedule slot is immutable'); END"
    ),
}


def _existing(connection):
    names = tuple(STATEMENTS)
    placeholders = ",".join("?" for _ in names)
    return dict(
        connection.execute(
            f"SELECT name,sql FROM sqlite_master WHERE name IN ({placeholders})", names
        )
    )


def validate_style_schedule(connection):
    if _existing(connection) != STATEMENTS:
        raise RuntimeError("foreign or incomplete style schedule schema")


def add_style_schedule(connection):
    existing = _existing(connection)
    if existing:
        validate_style_schedule(connection)
        return
    for statement in STATEMENTS.values():
        connection.execute(statement)
