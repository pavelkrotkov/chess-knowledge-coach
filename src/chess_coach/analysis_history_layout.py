"""Recognize the SQLite layouts covered by the aggregate capacity proof."""

from .analysis_history_columns import RUN_COLUMNS
from .analysis_history_columns import columns as _columns
from .analysis_history_native_layout import native as _native
from .analysis_history_source import _supported_triggers
from .analysis_history_stats_layout import supported as statistics_supported


def _run_index(connection):
    indexes = connection.execute("PRAGMA index_list(analysis_runs)").fetchall()
    if not indexes:
        return 0
    if len(indexes) != 1 or tuple(indexes[0][2:]) != (0, "c", 0):
        return None
    rows = connection.execute(
        "SELECT name,desc,coll,key FROM pragma_index_xinfo(?)", (indexes[0][1],)
    ).fetchall()
    keys = [tuple(row[:3]) for row in rows if row[3]]
    return 1 if keys == [("engine", 0, "BINARY")] else None


def _file(connection, source):
    # Overflow bounds below assume the entire 4 KiB page is usable.
    with source.open("rb") as stream:
        header = stream.read(21)
    return (
        len(header) >= 21
        and header[20] == 0
        and connection.execute("PRAGMA page_size").fetchone()[0] == 4096
        and connection.execute("PRAGMA encoding").fetchone()[0] == "UTF-8"
        and connection.execute("PRAGMA auto_vacuum").fetchone()[0] == 0
    )


def supported(connection, source, native):
    if not _database_layout(connection, source):
        return None
    try:
        _supported_triggers(connection)
    except ValueError:
        return None
    if native and not _native(connection):
        return None
    if not native and _partial(connection):
        return None
    return _run_index(connection)


def _partial(connection):
    row = connection.execute(
        """SELECT 1 FROM sqlite_schema WHERE name IN
        ('analysis_provenance','analysis_run_provenance',
         'analysis_provenance_settings','analysis_runs_read') LIMIT 1"""
    ).fetchone()
    return row is not None


def _database_layout(connection, source):
    return (
        _file(connection, source)
        and _columns(connection, "analysis_runs", RUN_COLUMNS)
        and _run_foreign_key(connection)
        and statistics_supported(connection)
    )


def _run_foreign_key(connection):
    rows = connection.execute("PRAGMA foreign_key_list(analysis_runs)").fetchall()
    return [tuple(row[2:]) for row in rows] == [
        ("games", "game_id", "id", "NO ACTION", "CASCADE", "NONE")
    ]
