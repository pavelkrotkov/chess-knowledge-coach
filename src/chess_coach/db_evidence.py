"""Preserve evidence while allowing unknown legacy observation times."""

from __future__ import annotations

import sqlite3


def _table_sql(schema: str) -> str:
    start = schema.index("CREATE TABLE IF NOT EXISTS evidence_mappings (")
    end = schema.index(";", start)
    return schema[start:end].replace(
        "CREATE TABLE IF NOT EXISTS evidence_mappings (", "CREATE TABLE evidence_mappings_new (", 1
    )


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def _dependent_tables(connection: sqlite3.Connection) -> list[str]:
    tables = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    result = []
    for (name,) in tables:
        quoted = name.replace('"', '""')
        refs = connection.execute(f'PRAGMA foreign_key_list("{quoted}")').fetchall()
        if any(ref[2] == "evidence_mappings" for ref in refs):
            result.append(name)
    return result


def rebuild_evidence(connection: sqlite3.Connection, schema: str) -> None:
    if _dependent_tables(connection):
        raise RuntimeError("cannot upgrade evidence with external foreign keys")
    old_columns = _columns(connection, "evidence_mappings")
    indexes = connection.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = 'evidence_mappings' "
        "AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY type, name"
    ).fetchall()
    connection.execute(_table_sql(schema))
    new_columns = _columns(connection, "evidence_mappings_new")
    if set(old_columns) - set(new_columns):
        raise RuntimeError("cannot upgrade evidence with unknown columns")
    select = [name if name in old_columns else "NULL" for name in new_columns]
    connection.execute(
        f"INSERT INTO evidence_mappings_new ({', '.join(new_columns)}) "
        f"SELECT {', '.join(select)} FROM evidence_mappings"
    )
    connection.execute("DROP TABLE evidence_mappings")
    connection.execute("ALTER TABLE evidence_mappings_new RENAME TO evidence_mappings")
    for (sql,) in indexes:
        connection.execute(sql)
