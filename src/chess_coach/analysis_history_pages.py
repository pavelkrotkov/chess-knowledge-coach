"""Conservative SQLite B-tree and overflow page bounds for supported layouts."""

PAGE_SIZE = 4096
# SQLite can address at most 2**32 pages; allow five sibling pages at
# every level of a 34-level tree during one balance operation.
SPLIT_PAGES_PER_TREE = 5 * 34


def overflow(payload, *, index=False):
    """Upper-bound overflow pages using SQLite's minimum local payload."""
    usable = PAGE_SIZE
    minimum = ((usable - 12) * 32 // 255) - 23
    maximum = ((usable - 12) * 64 // 255) - 23 if index else usable - 35
    if payload <= maximum:
        return 0
    return (payload - minimum + usable - 5) // (usable - 4)


def tree(records):
    """One leaf per record, at most one interior page per leaf, plus root."""
    return max(1, 2 * records + 1)


def replacement(inventory, *, engine_index, existing_links):
    rows = inventory["inventory_rows"]
    profiles = inventory["distinct_stored_profiles"]
    links = existing_links + rows
    # The updated original and its compact replacement can coexist.
    tree_count = 7 + 2 * engine_index
    pages = 2 * tree(rows) + tree(links) + 2 * tree(profiles)
    if engine_index:
        pages += 2 * tree(rows)
    pages += inventory["run_overflow_pages"] + inventory["original_run_overflow_pages"]
    pages += inventory["profile_overflow_pages"]
    pages += 2 * inventory["engine_index_overflow_pages"] if engine_index else 0
    pages += tree_count * SPLIT_PAGES_PER_TREE
    # Supported index builds require SQLite temporary storage in memory.
    return pages * PAGE_SIZE
