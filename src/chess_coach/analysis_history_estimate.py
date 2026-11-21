"""Conservative capacity bounds for the affected SQLite objects."""

import shutil

from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated


def _status(native, usage, required, free):
    if usage + RESERVE > PROJECT_LIMIT or free < RESERVE:
        return "insufficient"
    if native and usage + required <= PROJECT_LIMIT and free >= required:
        return "fits"
    return "unknown"


def estimate(connection, objects, native, source, root, deadline, pages, page_size):
    size = pages * page_size
    reusable = connection.execute("PRAGMA freelist_count").fetchone()[0] * page_size
    index_names = {
        row[0] for row in connection.execute("SELECT name FROM pragma_index_list('analysis_runs')")
    }
    index_bytes = sum(objects[name][0] for name in index_names)
    run_count = objects["analysis_runs"][3]
    # Bound table, profile, link and index insertions; 34 pages per insert
    # covers SQLite's maximum 32-bit page-number b-tree depth.
    replacement = (
        2 * (objects["analysis_runs"][0] + index_bytes)
        + run_count * (4 + len(index_names)) * 34 * page_size
        + MIN_WORKING
    )
    affected = sum(value[0] for value in objects.values()) + reusable + page_size
    if connection.execute("PRAGMA auto_vacuum").fetchone()[0]:
        affected = size
    affected_pages = min(pages, (affected + page_size - 1) // page_size)
    # Allow a maximum-sized sector header for each potentially journalled page.
    journal = affected_pages * (page_size + 65536 + 8) + MIN_WORKING
    working = max(MIN_WORKING, size // 10)
    usage = allocated(root, deadline)
    free = shutil.disk_usage(source.parent).free
    required = replacement + journal + working + RESERVE
    status = _status(native, usage, required, free)

    return (
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
    )
