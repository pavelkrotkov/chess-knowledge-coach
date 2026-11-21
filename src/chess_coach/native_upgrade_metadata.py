"""Bound the legacy schema and supported statistics pages."""

from .analysis_history_stats_layout import names
from .analysis_history_stats_layout import supported as statistics_supported


def _statistics(connection):
    if not statistics_supported(connection):
        raise ValueError("unsupported SQLite statistics")
    rows = connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name GLOB 'sqlite_*'"
    )
    if set(row[0] for row in rows) != set(names(connection)):
        raise ValueError("unsupported internal SQLite table")


def metadata_pages(connection, total_pages):
    _statistics(connection)
    sectors = {0, (total_pages - 1) // 16}
    count = 0
    for name in ("sqlite_schema", *names(connection)):
        found = 0
        for row in connection.execute("SELECT pageno FROM dbstat WHERE name=?", (name,)):
            page = row[0]
            if type(page) is not int or not 1 <= page <= total_pages:
                raise ValueError("metadata page unavailable")
            found += 1
            count += 1
            if count > 100_000:
                raise ValueError("metadata page inventory incomplete")
            sectors.add((page - 1) // 16)
        if not found:
            raise ValueError("metadata allocation unavailable")
    affected = sum(min(16, total_pages - sector * 16) for sector in sectors)
    return count, affected
