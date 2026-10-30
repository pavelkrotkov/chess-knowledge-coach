"""Create or validate isolated purpose request and attempt storage."""

from .purpose_schema_ddl import STATEMENTS


def add_purpose_analysis(connection):
    placeholders = ",".join("?" for _ in STATEMENTS)
    rows = connection.execute(
        f"SELECT name,sql FROM sqlite_master WHERE name IN ({placeholders})", tuple(STATEMENTS)
    )
    existing = {row[0]: row[1] for row in rows}
    if existing and existing != STATEMENTS:
        raise RuntimeError("foreign or incomplete purpose-analysis schema")
    if existing:
        return
    for statement in STATEMENTS.values():
        connection.execute(statement)
