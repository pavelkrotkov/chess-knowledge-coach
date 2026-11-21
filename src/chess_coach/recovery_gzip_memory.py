"""Require SQLite verification to keep temporary structures in memory."""

import sqlite3
from contextlib import closing


def compile_mode(connection):
    options = [row[0] for row in connection.execute("PRAGMA compile_options")]
    values = [value for value in options if value.startswith("TEMP_STORE=")]
    if len(values) != 1 or values[0] not in {"TEMP_STORE=1", "TEMP_STORE=2", "TEMP_STORE=3"}:
        raise ValueError("SQLite memory-only temporary storage unavailable")


def configure(connection):
    compile_mode(connection)
    if connection.execute("PRAGMA temp_store").fetchone()[0] != 2:
        connection.execute("PRAGMA temp_store=MEMORY")
    if connection.execute("PRAGMA temp_store").fetchone()[0] != 2:
        raise ValueError("SQLite memory-only temporary storage unavailable")


def probe():
    # This empty connection contains no source or restored database data.
    with closing(sqlite3.connect(":memory:")) as connection:
        configure(connection)
