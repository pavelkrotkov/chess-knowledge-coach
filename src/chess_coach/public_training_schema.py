"""Immutable licensed, direct-prompt training collections."""

import sqlite3


def add_public_training(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS public_collections (
        id INTEGER PRIMARY KEY, version TEXT NOT NULL UNIQUE, source_url TEXT NOT NULL,
        source_revision TEXT NOT NULL, source_sha256 TEXT NOT NULL, content_sha256 TEXT NOT NULL,
        source_format TEXT NOT NULL, license TEXT NOT NULL, attribution TEXT NOT NULL,
        license_notice TEXT NOT NULL, accepted INTEGER NOT NULL, excluded INTEGER NOT NULL,
        state TEXT NOT NULL CHECK(state IN (\u0027staging\u0027,\u0027ready\u0027)))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS public_tasks (
        collection_id INTEGER NOT NULL REFERENCES public_collections(id), task_id TEXT NOT NULL,
        prompt_fen TEXT NOT NULL, objective TEXT NOT NULL, lines_json TEXT NOT NULL,
        PRIMARY KEY(collection_id,task_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS public_exclusions (
        collection_id INTEGER NOT NULL REFERENCES public_collections(id), record_number INTEGER NOT NULL,
        reason TEXT NOT NULL, PRIMARY KEY(collection_id,record_number))""")
    for table in ("public_tasks", "public_exclusions"):
        for action in ("INSERT", "UPDATE", "DELETE"):
            _protect_child(connection, table, action)
    for action in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{action.lower()}_public_collections
            BEFORE {action} ON public_collections WHEN OLD.state=\u0027ready\u0027
            BEGIN SELECT RAISE(ABORT, \u0027ready public collection is immutable\u0027); END""")


def _protect_child(connection: sqlite3.Connection, table: str, action: str) -> None:
    refs = {"INSERT": ("NEW",), "UPDATE": ("OLD", "NEW"), "DELETE": ("OLD",)}[action]
    condition = " OR ".join(
        f"EXISTS (SELECT 1 FROM public_collections WHERE id={ref}.collection_id AND state=\u0027ready\u0027)"
        for ref in refs
    )
    connection.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{action.lower()}_{table}
        BEFORE {action} ON {table} WHEN {condition}
        BEGIN SELECT RAISE(ABORT, \u0027ready public collection is immutable\u0027); END""")
