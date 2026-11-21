"""Recognize the pinned SQLite and legacy layout covered by the upgrade proof."""

import os

from .native_upgrade_build import supported as build_supported
from .native_upgrade_metadata import metadata_pages
from .schema_compat_layout import validate


def _pages(connection, source, raw):
    pages = connection.execute("PRAGMA page_count").fetchone()[0]
    size = connection.execute("PRAGMA page_size").fetchone()[0]
    if type(pages) is not int:
        raise ValueError("unsupported SQLite page layout")
    info, current = os.fstat(raw.fileno()), source.stat()
    header = raw.read(21)
    checks = (
        (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino),
        pages > 0,
        size == 4096,
        current.st_size == pages * size,
        header[20:21] == bytes([0]),
        connection.execute("PRAGMA auto_vacuum").fetchone()[0] == 0,
        connection.execute("PRAGMA freelist_count").fetchone()[0] == 0,
        connection.execute("PRAGMA encoding").fetchone()[0] == "UTF-8",
    )
    if not all(checks):
        raise ValueError("unsupported SQLite page layout")
    return pages, size


def inspect(connection, source, raw):
    if not build_supported(connection):
        raise ValueError("unsupported SQLite build")
    if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
        raise ValueError("rollback journal required")
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("read-only inventory required")
    validate(connection)
    pages, size = _pages(connection, source, raw)
    metadata, affected = metadata_pages(connection, pages)
    return {
        "page_count": pages,
        "page_size": size,
        "metadata_pages": metadata,
        "metadata_sector_pages": affected,
    }
