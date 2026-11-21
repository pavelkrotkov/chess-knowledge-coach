"""Transactional analysis-history rebuild. Operational preconditions are external."""

import sqlite3
from pathlib import Path

from .analysis_history_assert import after_compaction, after_swap, schema
from .analysis_history_compact import compact as _compact
from .analysis_history_guard import check_storage, progress
from .analysis_history_links import links
from .analysis_history_plan import inspect
from .analysis_history_source import source as _source
from .analysis_history_swap import swap
from .analysis_history_verify import dependents, resolved
from .recovery_deadline import Deadline
from .recovery_fidelity import MAX_RECORD_BYTES


def _perform(connection, source, root, deadline):
    report = inspect(connection, source, root, deadline)
    if report["status"] != "fits":
        raise ValueError("conversion capacity not confirmed")
    connection.set_progress_handler(progress(source, root, report, deadline), 1000)
    before_schema = schema(connection)
    before_runs = resolved(connection, deadline)
    before_dependents = dependents(connection, deadline)
    before_links = links(connection, deadline)
    count, added_links = _compact(connection, deadline)
    compacted_dependents = after_compaction(
        connection, deadline, before_runs, before_dependents, before_links, count, added_links
    )
    swap(connection)
    after_swap(connection, deadline, before_schema, compacted_dependents, before_runs)
    check_storage(source, root, report, deadline)
    report["converted_rows"] = count
    report["all_runs_linked"] = True
    report["reusable_bytes_after"] = (
        connection.execute("PRAGMA freelist_count").fetchone()[0]
        * connection.execute("PRAGMA page_size").fetchone()[0]
    )
    return report


def convert(connection, project_root):
    """Run the real rebuild after independently verifying all operator preconditions.

    This is deliberately not exposed by a command: native #703 acceptance,
    verified separate recovery, writer quiescence and explicit capacity approval
    must be established before any production invocation.
    """
    root = Path(project_root).resolve(strict=True)
    source = _source(connection, root)
    deadline = Deadline()
    legacy = connection.execute("PRAGMA legacy_alter_table").fetchone()[0]
    old_limit = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
    connection.set_progress_handler(deadline.progress, 1000)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("PRAGMA legacy_alter_table=ON")
        connection.execute("BEGIN EXCLUSIVE")
        report = _perform(connection, source, root, deadline)
        connection.commit()
        try:
            report["physical_file_bytes_after"] = source.stat().st_size
        except OSError:
            report["physical_file_bytes_after"] = None
        return report
    except BaseException:
        connection.set_progress_handler(None, 0)
        connection.rollback()
        raise
    finally:
        connection.set_progress_handler(None, 0)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)
        connection.execute(f"PRAGMA legacy_alter_table={int(legacy)}")
        connection.execute("PRAGMA foreign_keys=ON")
