"""Additive durable protection allocations, preserving schema-30 slots."""

STATEMENTS = {
    "style_protection_allocations": (
        "CREATE TABLE style_protection_allocations (id INTEGER PRIMARY KEY, "
        "cycle_id INTEGER NOT NULL UNIQUE REFERENCES style_schedule_cycles(id), "
        "game_id INTEGER REFERENCES games(id), position_id INTEGER REFERENCES positions(id), "
        "evidence_id INTEGER REFERENCES evidence_mappings(id), "
        "binding_json TEXT CHECK(binding_json IS NULL OR json_valid(binding_json)), "
        "slot_id INTEGER REFERENCES style_schedule_slots(id), "
        "request_id INTEGER REFERENCES purpose_analysis_requests(id), "
        "status TEXT NOT NULL, detail TEXT NOT NULL)"
    ),
    "style_protection_rotation": (
        "CREATE TABLE style_protection_rotation (learner_key TEXT NOT NULL, "
        "game_id INTEGER NOT NULL REFERENCES games(id), "
        "next_index INTEGER NOT NULL CHECK(next_index>=0), PRIMARY KEY(learner_key,game_id))"
    ),
    "style_protection_identity": (
        "CREATE TRIGGER style_protection_identity BEFORE UPDATE OF cycle_id,game_id,position_id,"
        "evidence_id,binding_json,slot_id ON style_protection_allocations "
        "BEGIN SELECT RAISE(ABORT,'protection allocation is immutable'); END"
    ),
    "style_protection_request_once": (
        "CREATE TRIGGER style_protection_request_once BEFORE UPDATE OF request_id "
        "ON style_protection_allocations WHEN OLD.request_id IS NOT NULL "
        "AND NEW.request_id IS NOT OLD.request_id "
        "BEGIN SELECT RAISE(ABORT,'protection request is immutable'); END"
    ),
    "style_protection_no_delete": (
        "CREATE TRIGGER style_protection_no_delete BEFORE DELETE ON style_protection_allocations "
        "BEGIN SELECT RAISE(ABORT,'protection allocation is immutable'); END"
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


def validate(connection):
    if _existing(connection) != STATEMENTS:
        raise RuntimeError("foreign or incomplete protection schedule schema")


def add(connection):
    existing = _existing(connection)
    if existing:
        validate(connection)
        return
    for statement in STATEMENTS.values():
        connection.execute(statement)
