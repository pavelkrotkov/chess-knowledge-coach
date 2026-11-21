"""Conservative capacity bounds for the affected SQLite objects."""

import shutil

from .analysis_history_pages import replacement
from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated


def _status(native, usage, required, free):
    if usage + RESERVE > PROJECT_LIMIT or free < RESERVE:
        return "insufficient"
    if native and required is not None and usage + required <= PROJECT_LIMIT and free >= required:
        return "fits"
    return "unknown"


def estimate(
    connection, objects, native, source, root, deadline, pages, page_size, inventory, index
):
    size = pages * page_size
    reusable = connection.execute("PRAGMA freelist_count").fetchone()[0] * page_size
    index_names = {
        row[0] for row in connection.execute("SELECT name FROM pragma_index_list('analysis_runs')")
    }
    index_bytes = sum(objects[name][0] for name in index_names)
    run_count = objects["analysis_runs"][3]
    bound = None
    if index is not None and inventory["inventory_complete"]:
        links = objects.get("analysis_run_provenance", (0, 0, 0, 0))[3]
        bound = replacement(inventory, engine_index=index, existing_links=links)
        # The replacement DDL can temporarily duplicate schema payload and rebalance its tree.
        bound += 2 * objects["sqlite_schema"][0] + 5 * 34 * page_size
    affected = sum(value[0] for value in objects.values()) + reusable + page_size
    if connection.execute("PRAGMA auto_vacuum").fetchone()[0]:
        affected = size
    affected_pages = min(pages, (affected + page_size - 1) // page_size)
    # Retain the existing worst-case sector-header journal allowance.
    journal = affected_pages * (page_size + 65536 + 8) + MIN_WORKING
    working = max(MIN_WORKING, size // 10)
    usage = allocated(root, deadline)
    free = shutil.disk_usage(source.parent).free
    required = None if bound is None else bound + journal + working + RESERVE
    status = _status(native, usage, required, free)
    return (
        status,
        reusable,
        index_bytes,
        run_count,
        affected_pages,
        bound,
        journal,
        working,
        usage,
        free,
    )
