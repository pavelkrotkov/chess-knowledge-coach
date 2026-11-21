"""Bound SQLite and process memory in a dedicated operator process."""

import resource
import sqlite3

from .native_upgrade_available_memory import available

ADDRESS_BYTES = 1024 * 1024 * 1024
HEAP_BYTES = 512 * 1024 * 1024
HOST_RESERVE = 512 * 1024 * 1024


def _address_limit():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if any(value != resource.RLIM_INFINITY and value < ADDRESS_BYTES for value in (soft, hard)):
        raise ValueError("process address limit unavailable")
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_BYTES, hard))
    if resource.getrlimit(resource.RLIMIT_AS)[0] != ADDRESS_BYTES:
        raise ValueError("process address limit unavailable")


def configure():
    if available() < ADDRESS_BYTES + HOST_RESERVE:
        raise ValueError("memory admission unavailable")
    _address_limit()
    with sqlite3.connect(":memory:") as connection:
        if connection.execute(f"PRAGMA hard_heap_limit={HEAP_BYTES}").fetchone()[0] != HEAP_BYTES:
            raise ValueError("SQLite heap limit unavailable")
