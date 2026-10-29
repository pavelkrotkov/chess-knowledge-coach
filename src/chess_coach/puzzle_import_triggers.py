"""Keep staged corpus writes invisible to curriculum cursors and ready versions immutable."""

import sqlite3

VISIBLE = "('legacy_ready','ready')"


def install_corpus_triggers(connection: sqlite3.Connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='curriculum_source_revision'"
    ).fetchone()
    if not exists:
        raise ValueError("curriculum revision table is missing")
    _revision_triggers(connection)
    _immutable_corpora(connection)
    _immutable_children(connection, "puzzles")
    _immutable_children(connection, "puzzle_themes")
    _immutable_children(connection, "puzzle_import_seen")
    _immutable_children(connection, "puzzle_theme_counts")
    _immutable_children(connection, "puzzle_imports")


def _visible_condition(table: str, action: str) -> str:
    refs = {"INSERT": ("NEW",), "DELETE": ("OLD",), "UPDATE": ("OLD", "NEW")}[action]
    if table == "puzzle_corpora":
        return " OR ".join(f"{ref}.state IN {VISIBLE}" for ref in refs)
    return " OR ".join(
        f"EXISTS (SELECT 1 FROM puzzle_corpora WHERE id={ref}.corpus_id AND state IN {VISIBLE})"
        for ref in refs
    )


def _immutable_corpora(connection: sqlite3.Connection) -> None:
    for action in ("UPDATE", "DELETE"):
        connection.execute(
            f"""CREATE TRIGGER IF NOT EXISTS immutable_ready_corpus_{action.lower()} BEFORE {action}
            ON puzzle_corpora WHEN OLD.state='ready'
            BEGIN SELECT RAISE(ABORT, 'ready corpus is immutable'); END"""
        )


def _immutable_children(connection: sqlite3.Connection, table: str) -> None:
    for action in ("INSERT", "UPDATE", "DELETE"):
        refs = {"INSERT": ("NEW",), "DELETE": ("OLD",), "UPDATE": ("OLD", "NEW")}[action]
        condition = " OR ".join(
            f"EXISTS (SELECT 1 FROM puzzle_corpora WHERE id={ref}.corpus_id AND state='ready')"
            for ref in refs
        )
        connection.execute(
            f"""CREATE TRIGGER IF NOT EXISTS immutable_ready_{table}_{action.lower()} BEFORE {action} ON {table}
            WHEN {condition} BEGIN SELECT RAISE(ABORT, 'ready corpus is immutable'); END"""
        )


def _revision_triggers(connection: sqlite3.Connection) -> None:
    for table in ("puzzle_corpora", "puzzles"):
        for action in ("INSERT", "UPDATE", "DELETE"):
            name = f"curriculum_revision_{table}_{action.lower()}"
            connection.execute(f"DROP TRIGGER IF EXISTS {name}")
            condition = _visible_condition(table, action)
            connection.execute(
                f"""CREATE TRIGGER {name} AFTER {action} ON {table} WHEN {condition}
                BEGIN UPDATE curriculum_source_revision SET revision=revision+1 WHERE id=1; END"""
            )
