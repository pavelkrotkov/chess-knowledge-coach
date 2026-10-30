"""Backfill a derived, invalidatable game-start projection transactionally."""

from .style_time_ddl import STATEMENTS
from .style_time_projection import update_projection


def existing_projection(connection):
    placeholders = ",".join("?" for _ in STATEMENTS)
    rows = connection.execute(
        f"SELECT name,sql FROM sqlite_master WHERE name IN ({placeholders})", tuple(STATEMENTS)
    )
    existing = {row[0]: row[1] for row in rows}
    if not existing:
        return False
    if existing != STATEMENTS:
        raise RuntimeError("foreign or incomplete style time projection")
    return True


def ingest_projection_available(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    present = existing_projection(connection)
    if version < 28:
        if present:
            raise RuntimeError("style time projection exists under legacy schema")
        return False
    if version != 28 or not present:
        raise RuntimeError("unsupported or missing style time projection")
    return True


def add_style_game_times(connection):
    if existing_projection(connection):
        return
    for statement in STATEMENTS.values():
        connection.execute(statement)
    connection.execute(
        "INSERT INTO style_game_times(game_id,version,status) SELECT id,?,? FROM games",
        ("", "stale"),
    )
    for (game_id,) in connection.execute("SELECT id FROM games ORDER BY id"):
        update_projection(connection, game_id)
