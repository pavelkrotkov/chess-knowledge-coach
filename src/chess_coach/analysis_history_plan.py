"""Read-only, bounded planning for compacting historical analysis settings."""

import sqlite3
from pathlib import Path

from .analysis_history_estimate import estimate
from .analysis_history_inventory import inventory, limits
from .analysis_history_layout import supported
from .analysis_history_stats import allocation
from .recovery_capacity import PROJECT_LIMIT, RESERVE, snapshot
from .recovery_copy import pinned
from .recovery_deadline import Deadline
from .recovery_fidelity import MAX_RECORD_BYTES


def inspect(connection, source, root, deadline):
    """Estimate a same-database rebuild; estimates do not reserve storage."""
    pages, page_size = snapshot(connection)
    size = pages * page_size
    objects, native = allocation(connection)
    index = supported(connection, source, native)
    profile = (
        inventory(connection, deadline, native=native, engine_index=index)
        if index is not None
        else {"inventory_complete": False, "inventory_limits": limits()}
    )
    # Reconcile the full scan against both SQL's table count and dbstat leaf cells.
    if profile["inventory_complete"]:
        count = connection.execute("SELECT count(*) FROM analysis_runs").fetchone()[0]
        if profile["inventory_rows"] != count or count != objects["analysis_runs"][3]:
            profile = {"inventory_complete": False, "inventory_limits": limits()}
    (
        status,
        reusable,
        index_bytes,
        run_count,
        affected_pages,
        replacement,
        journal,
        working,
        usage,
        free,
    ) = estimate(
        connection, objects, native, source, root, deadline, pages, page_size, profile, index
    )
    return {
        "status": status,
        "analysis_table_bytes": objects["analysis_runs"][0],
        "analysis_table_payload_bytes": objects["analysis_runs"][1],
        "analysis_table_unused_bytes": objects["analysis_runs"][2],
        "analysis_index_bytes": index_bytes,
        "statistics_table_bytes": sum(
            objects.get(name, (0,))[0] for name in ("sqlite_stat1", "sqlite_stat4")
        ),
        "analysis_run_count": run_count,
        "native_provenance_tables_available": native,
        "supported_layout": index is not None,
        "index_memory_temp_required": bool(index),
        "journal_affected_pages_bound": affected_pages,
        "database_bytes": size,
        "physical_file_bytes": source.stat().st_size,
        "existing_reusable_bytes": reusable,
        "replacement_and_index_bound_bytes": replacement,
        "physical_growth_bound_bytes": replacement,
        "future_reusable_bytes_min": 0,
        "future_reusable_bytes_max": None,
        "separate_restore_snapshot_bytes": size,
        "independent_backup_bytes": None,
        "rollback_journal_bound_bytes": journal,
        "working_bytes": working,
        "reserve_bytes": RESERVE,
        "project_allocated_bytes": usage,
        "project_limit_bytes": PROJECT_LIMIT,
        "filesystem_free_bytes": free,
        "scope": (
            "Conservative point-in-time bounds, not a reservation or predicted file reduction. "
            "Unknown means the conservative bound did not establish a fit. "
            "Separate recovery storage is not included."
        ),
        **profile,
    }


def plan(source, project_root):
    """Open the source read-only without initializing or migrating it."""
    root = Path(project_root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    if not root.is_dir() or not source.is_file() or not source.is_relative_to(root):
        raise ValueError("source database must be an existing file inside the project")
    deadline = Deadline()
    with pinned(source, deadline, require_memory=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
        return inspect(connection, source, root, deadline)
